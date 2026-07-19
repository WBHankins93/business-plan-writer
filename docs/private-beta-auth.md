# Private Beta Authentication and Save/Resume

## System architecture

```mermaid
flowchart LR
    subgraph Browser["Browser"]
        Public["Public pages<br/>/, /login, /register"]
        Private["Private pages<br/>/projects/*"]
        DemoUI["Explicit demo<br/>/demo"]
        Session["Supabase SSR session cookies"]
    end

    subgraph Identity["Supabase Auth"]
        Auth["Email/password registration and login"]
        Claims["Access + refresh tokens"]
        JWKS["Public JWKS<br/>asymmetric keys"]
        Legacy["/auth/v1/user<br/>legacy HS256 validation"]
    end

    subgraph Web["Next.js web application"]
        Guard["Middleware<br/>getClaims + token refresh"]
        UI["Project list and intake workspace"]
        Signout["Server-side logout route"]
    end

    subgraph API["FastAPI application"]
        Verify["Bearer-token verifier"]
        Routes["Owned project, run,<br/>and artifact routes"]
        DemoAPI["/demo/* routes<br/>feature-flagged"]
        Worker["Plan-generation worker"]
    end

    subgraph Persistence["Persistence"]
        DB[("Projects, drafts, runs,<br/>and ownership metadata")]
        Files[("Run-scoped artifacts")]
    end

    Public --> Auth
    Auth --> Claims --> Session
    Session --> Guard
    Guard -->|"valid or refreshed claims"| Private
    Private --> UI
    UI -->|"Authorization: Bearer access token"| Verify
    Verify -->|"ES256 / RS256"| JWKS
    Verify -.->|"legacy HS256 only"| Legacy
    Verify --> Routes
    Routes -->|"WHERE id = resource_id<br/>AND owner_id = token.sub"| DB
    Routes --> Worker --> Files
    Routes --> Files
    Signout --> Auth
    DemoUI --> DemoAPI
    DemoAPI --> Worker

    classDef public fill:#eef3fb,stroke:#255fd4,color:#17213d;
    classDef private fill:#e8f6ef,stroke:#237a59,color:#17213d;
    classDef warning fill:#fff5dc,stroke:#9a5a00,color:#17213d;
    class Public,Auth,Claims,JWKS,Legacy public;
    class Private,Session,Guard,UI,Verify,Routes,DB,Files,Worker,Signout private;
    class DemoUI,DemoAPI warning;
```

The two enforcement layers have different jobs: Next.js middleware protects navigation and
refreshes cookies, while FastAPI independently verifies every bearer token and enforces database
ownership. Bypassing the browser guard therefore does not grant access to private data.

## Registration, login, and session workflow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Page as Login / Register page
    participant Auth as Supabase Auth
    participant Cookie as SSR session cookies
    participant Guard as Next.js middleware
    participant Projects as /projects

    User->>Page: Submit email and password
    Page->>Auth: signUp or signInWithPassword
    alt Registration requires email confirmation
        Auth-->>Page: User created, no active session
        Page-->>User: Check email, then sign in
    else Session issued
        Auth-->>Page: Access token + refresh token
        Page->>Cookie: Persist session
        Page->>Projects: Navigate after authentication
        Projects->>Guard: Request with cookies
        Guard->>Auth: getClaims and refresh when needed
        alt Claims valid
            Guard-->>Projects: Continue with refreshed cookies
            Projects-->>User: Show owned projects
        else Missing or invalid session
            Guard-->>User: Redirect to /login?next=/projects
        end
    end
```

## Authenticated API and ownership workflow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Authenticated browser UI
    participant SDK as Supabase browser client
    participant API as FastAPI route
    participant Verify as Token verifier
    participant Keys as Supabase JWKS / Auth server
    participant Store as Project or Run store
    participant DB as Database

    User->>UI: Open, save, generate, poll, or download
    UI->>SDK: Read current session
    SDK-->>UI: Access token
    UI->>API: Request + Authorization: Bearer token
    API->>Verify: Verify token
    Verify->>Keys: Resolve signing key or validate legacy token
    Keys-->>Verify: Verified identity claims
    Verify-->>API: AuthenticatedUser(token.sub)
    API->>Store: Query(resource_id, token.sub)
    Store->>DB: SELECT / UPDATE by id AND owner_id
    alt Resource belongs to user
        DB-->>Store: Owned row
        Store-->>API: Resource
        API-->>UI: Success
    else Missing or owned by someone else
        DB-->>Store: No row
        Store-->>API: None
        API-->>UI: 404 without ownership disclosure
    end
```

The browser never supplies a trusted user ID. It receives only a Supabase publishable key; the
API does not use or require a service-role credential. Asymmetric Supabase JWTs are verified
against the project's JWKS. Legacy HS256 tokens are validated by Supabase Auth's `/user`
endpoint with the publishable key, not with a shared JWT signing secret.

## Expired-session and logout workflow

```mermaid
flowchart TD
    Request["User requests /projects/*"] --> Guard["Middleware validates claims"]
    Guard --> Valid{"Session state?"}
    Valid -->|"Valid claims"| Continue["Continue to private page"]
    Valid -->|"Refreshable"| Refresh["Supabase refreshes session<br/>and middleware updates cookies"]
    Refresh --> Continue
    Valid -->|"Missing or invalid"| Login["Redirect to /login with safe next path"]

    APIRequest["Private API returns 401"] --> Clear["Browser clears local Supabase session"]
    Clear --> Login

    Logout["User submits Logout"] --> Route["POST /auth/signout"]
    Route --> Revoke["Supabase signOut"]
    Revoke --> ClearCookies["Clear session cookies"]
    ClearCookies --> Login
```

## Compact auth flow map

```text
Register / Login
  -> Supabase Auth issues access + refresh tokens
  -> @supabase/ssr stores the session in cookies
  -> Next.js middleware validates/refreshes claims for /projects/*
  -> browser sends the access token as Authorization: Bearer to FastAPI
  -> FastAPI verifies issuer, audience, expiry, signature, and token subject
  -> database queries use that verified subject as owner_id

Logout
  -> server route signs out with Supabase
  -> session cookies are cleared
  -> user returns to /login
```

## Protected-route map

| Route | Protection | Ownership behavior |
|---|---|---|
| `/projects` and `/projects/[projectId]` | Next.js middleware | Redirects missing/expired browser sessions to login |
| `POST/GET /projects` | FastAPI bearer token | Creates/lists records for verified token subject only |
| `GET /projects/{id}` | FastAPI bearer token | Queries by project ID and verified owner ID; otherwise 404 |
| `PUT /projects/{id}/draft` | FastAPI bearer token | Updates by project ID and verified owner ID; ignores extra client fields |
| `POST /projects/{id}/generate-plan` | FastAPI bearer token | Generates from the owned server-saved draft |
| `GET /runs/{id}` | FastAPI bearer token | Queries by run ID and verified owner ID |
| `GET /runs/{id}/artifacts/{filename}` | FastAPI bearer token | Requires the run owner and an indexed artifact filename |
| `/demo` and `/demo/*` | Explicit demo flag | Separate ownerless fixture flow; API disabled unless `ENABLE_DEMO_MODE=true` |

## Saved-draft behavior

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Intake workspace
    participant Queue as Serialized save queue
    participant API as PUT /projects/{id}/draft
    participant DB as Owned project row

    User->>UI: Edit a field or change step
    UI-->>User: Show "Unsaved changes"
    UI->>UI: Debounce for 900 ms
    UI->>Queue: Enqueue canonical intake + current step
    Queue-->>User: Show "Saving..."
    Queue->>API: Bearer-authenticated save
    API->>DB: UPDATE WHERE id = project_id AND owner_id = token.sub
    alt Save succeeds
        DB-->>API: Updated project
        API-->>Queue: Persisted timestamp and draft
        Queue-->>User: Show "Saved"
    else Save fails
        API-->>Queue: Error
        Queue-->>User: Keep edits in memory and show "Retry save"
        User->>Queue: Retry
        Queue->>API: Repeat latest serialized save
    end

    User->>UI: Refresh or reopen project URL
    UI->>API: GET /projects/{id} with bearer token
    API->>DB: SELECT WHERE id AND owner_id match
    DB-->>API: Saved intake + current step
    API-->>UI: Owned project payload
    UI-->>User: Resume from persisted progress

    User->>UI: Generate plan
    UI->>Queue: Force latest save and await success
    Queue-->>UI: Saved
    UI->>API: POST /projects/{id}/generate-plan
    API->>DB: Read server-saved owned draft
```

- A new project is created before the intake opens.
- Field and step changes are debounced for 900 ms, then canonicalized and saved to the project's
  `intake_json` and `current_step` fields.
- The UI shows `Unsaved changes`, `Saving…`, `Saved`, or `Save failed`.
- Failed saves retain the in-memory edits, warn against leaving/refreshing, and expose a retry.
- Generation forces a successful save first, then the API generates from the database copy.
- Opening a saved project or refreshing its URL reloads the persisted intake and step.
- The projects screen lists drafts by most recently saved and links directly to resume them.

## Deployment notes and residual risks

- Apply `alembic upgrade head` before starting the API.
- Configure matching Supabase URL/publishable keys for API and web. Configure Supabase redirect
  URLs and email-confirmation behavior for the deployed origin.
- Keep `ENABLE_DEMO_MODE=false` unless a public demo is intended. When enabled, demo generation
  needs deployment-level rate limiting/cost controls because it intentionally has no login.
- Local-disk artifacts and in-process background jobs remain single-host beta constraints. Moving
  to multiple API hosts requires shared object storage and a durable queue.
- There is no server-side token revocation lookup for asymmetric JWTs between issuance and their
  short expiry. Supabase session expiry settings bound that window; legacy HS256 validation does
  perform an Auth-server lookup.
- Autosave uses last-write-wins. Concurrent editing of the same project in multiple tabs/devices
  can overwrite a newer draft; optimistic version checks are deferred beyond the minimum beta.

# Multi-user beta database model

## Entity relationship summary

```text
profiles 1 ── * projects 1 ── 1 intake_drafts
                         └── * runs 1 ── * run_events
                                    ├── * artifacts
                                    └── * revisions ── 1 artifacts
                                              └── parent_revision_id → revisions.id
```

- `profiles` stores only application lifecycle metadata for an external auth user. It does
  not store passwords, sessions, provider tokens, API keys, or billing state.
- `projects` is the ownership and retention root for one business plan. A client slug remains
  presentation metadata on a run and is never an ownership or uniqueness key.
- `intake_drafts` is the one mutable saved intake workspace for a project. The unique
  `project_id` constraint prevents duplicate current drafts.
- `runs` stores execution state plus immutable input and non-secret model configuration
  snapshots. Outputs are a small summary plus related artifact metadata.
- `run_events` is the append-only audit history. Every queued/running/succeeded/failed
  transition adds a row; event rows are never updated by application code.
- `artifacts` stores a provider and opaque storage key, content type, and artifact type. File
  content stays in filesystem/object storage.
- `revisions` gives generated drafts an explicit lineage. Revision `0` is the original draft;
  each later revision has a parent and an increasing per-run revision number.

There is deliberately no payment table in this migration. Payment state belongs in a separate
bounded model when checkout is implemented; it must not be added to projects or runs.

## Ownership rules

Application stores scope project, draft, run, and revision operations through the project owner.
A cross-owner lookup returns no row, so callers do not disclose whether another user's ID exists.

On PostgreSQL, the migration enables row-level security on all seven owned tables. Policies compare
ownership to `current_setting('app.current_user_id', true)`. A trusted authentication adapter must
run `SET LOCAL app.current_user_id = '<authenticated profile id>'` in each user transaction. The
runtime role must not own these tables and must not have `BYPASSRLS`; migrations should use a
separate owner role. `run_events` has select/insert policies only and revokes public update/delete.

SQLite is supported for local development and migration tests, but it has no row-level security.
The owner-scoped store methods are therefore the security boundary in SQLite tests.

## Retention and deletion policy

- A user project deletion is a soft delete. The default recovery window is 30 days, recorded in
  `deleted_at` and `purge_after`; deleted projects disappear from normal owned reads immediately.
- Account deletion timestamps the profile and all of its projects with the same recovery window.
- A retention job queries `ProjectStore.due_for_purge()`. For each due project it must first delete
  every referenced object from external storage, then call `ProjectStore.purge()`.
- Hard-deleting a project cascades through its draft, runs, audit events, artifact metadata, and
  revisions. Audit history is therefore immutable during the retention window and removed with the
  sensitive project at final purge.
- A purge is not considered complete until external objects are gone. Failed object deletion must
  leave the database tombstone in place for retry.
- Database backups can retain deleted rows beyond the live-database purge. Production backup
  expiry and restore procedures must use a documented maximum retention period, and restored data
  must rerun overdue purges before serving traffic.

## Migration strategy

Migration `20260719_0003` creates the owned tables, backfills every existing run into a legacy
profile/project/draft, snapshots unknown legacy model configuration explicitly, converts embedded
file names into artifact references, and numbers an existing draft as revision `0`. It removes the
duplicate run artifact path and embedded artifact-file list. The downgrade reconstructs the old
shape before removing the beta tables.

## Beta scale limitations

- One mutable intake draft per project is intentional. Whole-document JSON saves have no optimistic
  concurrency control, so simultaneous editing in multiple browser tabs is last-write-wins.
- Run progress rewrites one small JSON document and run events are unpartitioned. Revisit when event
  volume or per-user history makes indexed queries insufficient.
- Local filesystem artifacts support only a single persistent API host. Multi-instance deployment
  requires an object-store provider implementation while retaining the same artifact references.
- The retention primitives are implemented, but a scheduled purge worker and storage-provider
  deletion adapter are operational deployment work.
- PostgreSQL RLS depends on a trusted request-to-transaction identity adapter. Login UI and session
  issuance are outside this change; the existing API-key endpoint remains a compatibility path and
  must not be treated as multi-user authorization.
- There is no billing ledger, entitlement engine, collaboration/sharing model, organization model,
  event partitioning, or data warehouse in this beta schema.

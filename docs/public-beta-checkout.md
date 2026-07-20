# Public Beta Checkout Contract

## Offer

The release supports one package only: **Funding-Focused Business Plan Service**, `$750 USD`
by default as a one-time purchase. It includes one funding-focused plan, DOCX/PDF delivery,
two revisions, delivery within seven calendar days after the intake is accepted as complete,
and human review during the beta. `FUNDING_READY_PRICE_CENTS` and
`FUNDING_READY_CURRENCY` are server settings; the browser cannot choose an amount or package.

## Checkout and confirmation flow

1. An authenticated owner calls `POST /billing/checkout-sessions`.
2. The server snapshots the package amount/currency in a `checkout_pending` payment and
   creates a Stripe-hosted one-time Checkout Session with the same server-side values.
3. Stripe redirects the browser to the configured success or cancel URL. Neither redirect
   changes payment state or grants access.
4. The browser polls `GET /billing/payments/{payment_id}`.
5. Only a signature-verified `checkout.session.completed` with `payment_status=paid`, the
   expected mode, amount, and currency changes the payment to `paid` and grants one credit.

Authenticated endpoints verify the Supabase bearer token server-side and derive ownership from
its subject. Client-provided owner or payment state is never trusted.

## State machines

Payment:

`checkout_pending → processing | paid | failed | abandoned`

`paid → partially_refunded → refunded` (a full refund can also move `paid → refunded`)

Entitlement:

`available → reserved → consumed`

`reserved → available` when generation fails. A successful full refund moves any current
entitlement state to `refunded`; a failed run never reopens a refunded credit.

Generation remains independently `queued → running → succeeded | failed`. Payment stays
`paid` when generation fails, while the entitlement returns to `available` for a retry.

## Webhook behavior

The endpoint uses Stripe's raw request body and `Stripe-Signature` with
`STRIPE_WEBHOOK_SECRET`. Each event ID is inserted transactionally before its state change.
Duplicate delivery returns `200` without repeating the change. A unique entitlement per
payment also prevents two logically equivalent completion events from granting two credits.

Handled events:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`
- `payment_intent.payment_failed`
- `refund.created`, `refund.updated`, and `refund.failed`

Configure the Stripe endpoint to send only those events. Unrecognized or unmapped events are
recorded as ignored and acknowledged. Invalid signatures return `400`; database/configuration
failures return non-2xx so Stripe retries.

## Failure, refund, and support behavior

- Checkout creation failures persist as failed payment attempts without exposing Stripe errors.
- Failed or expired payments never create an entitlement.
- Generation reserves a credit atomically with run creation. Success consumes it; timeout or
  failure releases it.
- Successful partial refunds are recorded and leave the entitlement usable pending an explicit
  policy decision. Successful cumulative refunds equal to the purchase amount revoke it.
- `POST /billing/support-requests` records idempotent payment, refund, generation, or human-QA
  requests linked to the owner's payment/run. It does not issue money automatically; refunds
  are authorized in Stripe and reconciled by webhook.

## Stripe test mode

Set `STRIPE_SECRET_KEY=sk_test_...` and the test endpoint's
`STRIPE_WEBHOOK_SECRET=whsec_...`, apply migrations, and forward events locally:

```bash
alembic upgrade head
stripe listen --forward-to localhost:8000/billing/webhooks/stripe
uvicorn web_api.app:app --reload --port 8000
```

Live keys are rejected unless `STRIPE_ALLOW_LIVE_MODE=true`. No Stripe secret belongs in a
`NEXT_PUBLIC_` variable or frontend bundle.

## Unresolved financial and legal decisions

- Confirm whether sales tax must be collected by buyer jurisdiction for the `$750 USD` offer.
- Publish the refund window, partial-refund policy, and treatment of already-delivered work.
- Define the exact boundaries of a revision versus a new business concept.
- Confirm how the seven-calendar-day promise handles customer delays after intake acceptance.
- Define the human-review checklist, service level, and backup reviewer.
- Approve checkout terms, privacy language, AI-assistance disclosure, and the disclaimer that
  output is not legal, tax, investment, or lending advice.

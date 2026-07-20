from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import stripe
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web_api import db as db_module
from web_api.config import (
    checkout_cancel_url,
    checkout_success_url,
    generation_configuration,
    stripe_secret_key,
    stripe_webhook_secret,
)
from web_api.packages import FUNDING_READY, PackageDefinition


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _provider_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    candidate = _value(value, "id")
    return candidate if isinstance(candidate, str) else None


def _url_with_query(url: str, **params: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class EntitlementUnavailable(RuntimeError):
    pass


class BillingConfigurationError(RuntimeError):
    pass


class InvalidWebhook(ValueError):
    pass


@dataclass(frozen=True)
class CheckoutSessionResult:
    id: str
    url: str
    livemode: bool


class StripeGateway:
    """Small provider boundary so tests never make Stripe network calls."""

    def create_checkout_session(
        self, *, payment_id: str, package: PackageDefinition
    ) -> CheckoutSessionResult:
        try:
            secret_key = stripe_secret_key()
            success_url = _url_with_query(checkout_success_url(), payment_id=payment_id)
            session = stripe.checkout.Session.create(
                api_key=secret_key,
                idempotency_key=payment_id,
                mode="payment",
                client_reference_id=payment_id,
                metadata={"payment_record_id": payment_id, "package_code": package.code},
                payment_intent_data={
                    "metadata": {"payment_record_id": payment_id, "package_code": package.code}
                },
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": package.currency,
                            "unit_amount": package.price_cents,
                            "product_data": {
                                "name": package.name,
                                "description": package.description,
                            },
                        },
                    }
                ],
                success_url=success_url,
                cancel_url=checkout_cancel_url(),
            )
        except RuntimeError as exc:
            raise BillingConfigurationError(str(exc)) from exc
        session_id = _provider_id(session)
        url = _value(session, "url")
        if not session_id or not isinstance(url, str):
            raise RuntimeError("Stripe did not return a usable Checkout Session")
        return CheckoutSessionResult(
            id=session_id,
            url=url,
            livemode=bool(_value(session, "livemode", "_live_" in secret_key)),
        )

    def construct_event(self, payload: bytes, signature: str | None) -> Any:
        if not signature:
            raise InvalidWebhook("Missing Stripe-Signature header")
        try:
            return stripe.Webhook.construct_event(payload, signature, stripe_webhook_secret())
        except Exception as exc:  # Stripe exposes different exception paths across SDK majors.
            if isinstance(exc, RuntimeError):
                raise BillingConfigurationError(str(exc)) from exc
            raise InvalidWebhook("Stripe webhook signature verification failed") from exc


class BillingStore:
    """Transactional payment, webhook, entitlement, and support persistence."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or db_module.SessionLocal

    def start_checkout(self, owner_id: str, package: PackageDefinition = FUNDING_READY):
        from web_api.models import Payment, Profile

        with self.session_factory() as db:
            if db.get(Profile, owner_id) is None:
                return None
            payment = Payment(
                id=str(uuid.uuid4()),
                owner_id=owner_id,
                package_code=package.code,
                provider="stripe",
                status="checkout_pending",
                amount_total=package.price_cents,
                currency=package.currency,
                provider_livemode="_live_" in stripe_secret_key(),
            )
            db.add(payment)
            db.commit()
            db.refresh(payment)
            db.expunge(payment)
            return payment

    def attach_checkout(self, payment_id: str, session: CheckoutSessionResult) -> None:
        from web_api.models import Payment

        with self.session_factory() as db:
            payment = db.get(Payment, payment_id)
            if payment is None:
                raise LookupError("Payment record disappeared during checkout")
            payment.provider_checkout_session_id = session.id
            payment.provider_livemode = session.livemode
            db.commit()

    def fail_checkout_creation(self, payment_id: str, message: str) -> None:
        from web_api.models import Payment

        with self.session_factory() as db:
            payment = db.get(Payment, payment_id)
            if payment is None:
                return
            payment.status = "failed"
            payment.failure_code = "checkout_creation_failed"
            payment.failure_message = message[:1000]
            db.commit()

    def get_payment_owned(self, payment_id: str, owner_id: str):
        from web_api.models import Payment

        with self.session_factory() as db:
            payment = db.scalar(
                select(Payment).where(Payment.id == payment_id, Payment.owner_id == owner_id)
            )
            if payment is None:
                return None
            db.expunge(payment)
            return payment

    def entitlement_for_payment(self, payment_id: str):
        from web_api.models import Entitlement

        with self.session_factory() as db:
            entitlement = db.scalar(
                select(Entitlement).where(Entitlement.payment_id == payment_id)
            )
            if entitlement is None:
                return None
            db.expunge(entitlement)
            return entitlement

    def entitlement_summary(self, owner_id: str) -> dict[str, Any]:
        from web_api.models import Entitlement

        with self.session_factory() as db:
            entitlements = db.scalars(
                select(Entitlement)
                .where(Entitlement.owner_id == owner_id)
                .order_by(Entitlement.created_at)
            ).all()
            return {
                "available_credits": sum(item.status == "available" for item in entitlements),
                "entitlements": [
                    {
                        "id": item.id,
                        "package_code": item.package_code,
                        "status": item.status,
                        "revision_limit": item.revision_limit,
                        "revisions_used": item.revisions_used,
                    }
                    for item in entitlements
                ],
            }

    def create_paid_run(
        self,
        *,
        owner_id: str,
        run_id: str,
        client_slug: str,
        intake: dict,
        title: str,
        project_id: str | None = None,
    ) -> str:
        """Atomically reserve one credit and queue an owner-scoped generation."""
        from web_api.models import Entitlement, IntakeDraft, Project, Run, RunEvent

        with self.session_factory() as db:
            entitlement = db.scalar(
                select(Entitlement)
                .where(Entitlement.owner_id == owner_id, Entitlement.status == "available")
                .order_by(Entitlement.activated_at, Entitlement.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if entitlement is None:
                raise EntitlementUnavailable("No paid generation credit is available")
            reserved = db.execute(
                update(Entitlement)
                .where(Entitlement.id == entitlement.id, Entitlement.status == "available")
                .values(status="reserved", reserved_run_id=run_id)
            )
            if reserved.rowcount != 1:
                raise EntitlementUnavailable("The available credit was already reserved")

            project = None
            if project_id:
                project = db.scalar(
                    select(Project).where(
                        Project.id == project_id,
                        Project.owner_id == owner_id,
                        Project.deleted_at.is_(None),
                    )
                )
                if project is None:
                    raise LookupError("Project not found")
            if project is None:
                project = Project(owner_id=owner_id, title=(title[:160] or "Untitled business"))
                db.add(project)
                db.flush()
            draft = db.scalar(select(IntakeDraft).where(IntakeDraft.project_id == project.id))
            if draft is None:
                db.add(IntakeDraft(project_id=project.id, data_json=intake))
            else:
                draft.data_json = intake
                draft.updated_at = utc_now_naive()
            provider, model, generation_config = generation_configuration()
            db.add(
                Run(
                    id=run_id,
                    project_id=project.id,
                    entitlement_id=entitlement.id,
                    client_slug=client_slug,
                    status="queued",
                    input_snapshot_json=intake,
                    progress_json=db_module.initial_progress(),
                    provider=provider,
                    model=model,
                    configuration_json={
                        **generation_config,
                        "package_code": entitlement.package_code,
                    },
                )
            )
            db.add(RunEvent(run_id=run_id, kind="status", status="queued", message="Run queued."))
            db.commit()
            return entitlement.id

    def process_event(self, event: Any) -> dict[str, Any]:
        from web_api.models import WebhookEvent

        event_id = str(_value(event, "id", ""))
        event_type = str(_value(event, "type", ""))
        data = _value(event, "data", {})
        obj = _value(data, "object", {})
        object_id = _provider_id(obj)
        if not event_id or not event_type:
            raise ValueError("Stripe event is missing an id or type")

        try:
            with self.session_factory() as db:
                if db.get(WebhookEvent, event_id) is not None:
                    return {"duplicate": True, "handled": True}
                receipt = WebhookEvent(
                    provider_event_id=event_id,
                    event_type=event_type,
                    provider_object_id=object_id,
                    status="processing",
                )
                db.add(receipt)
                db.flush()
                handled = self._dispatch_event(db, event_type, obj, bool(_value(event, "livemode")))
                receipt.status = "processed" if handled else "ignored"
                receipt.processed_at = utc_now_naive()
                db.commit()
                return {"duplicate": False, "handled": handled}
        except IntegrityError:
            with self.session_factory() as db:
                if db.get(WebhookEvent, event_id) is not None:
                    return {"duplicate": True, "handled": True}
            raise

    def _dispatch_event(self, db: Session, event_type: str, obj: Any, livemode: bool) -> bool:
        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            return self._complete_checkout(db, obj, livemode)
        if event_type == "checkout.session.async_payment_failed":
            return self._fail_checkout(db, obj, "async_payment_failed")
        if event_type == "checkout.session.expired":
            return self._abandon_checkout(db, obj)
        if event_type == "payment_intent.payment_failed":
            return self._fail_payment_intent(db, obj)
        if event_type in {"refund.created", "refund.updated", "refund.failed"}:
            return self._record_refund(db, obj)
        return False

    @staticmethod
    def _checkout_payment(db: Session, obj: Any):
        from web_api.models import Payment

        session_id = _provider_id(obj)
        payment = db.scalar(
            select(Payment).where(Payment.provider_checkout_session_id == session_id)
        )
        if payment is not None:
            return payment
        reference = _value(obj, "client_reference_id")
        if isinstance(reference, str):
            candidate = db.get(Payment, reference)
            if candidate is not None and candidate.provider_checkout_session_id in {None, session_id}:
                candidate.provider_checkout_session_id = session_id
                return candidate
        return None

    def _complete_checkout(self, db: Session, obj: Any, livemode: bool) -> bool:
        from web_api.models import Entitlement

        payment = self._checkout_payment(db, obj)
        if payment is None:
            return False
        if payment.provider_livemode != livemode:
            payment.status = "failed"
            payment.failure_code = "stripe_mode_mismatch"
            payment.failure_message = "Webhook mode did not match checkout mode."
            return True
        payment.provider_payment_intent_id = _provider_id(_value(obj, "payment_intent"))
        if _value(obj, "payment_status") != "paid":
            payment.status = "processing"
            return True
        amount_total = int(_value(obj, "amount_total", -1))
        currency = str(_value(obj, "currency", "")).lower()
        if amount_total != payment.amount_total or currency != payment.currency:
            payment.status = "failed"
            payment.failure_code = "checkout_amount_mismatch"
            payment.failure_message = "Paid amount or currency did not match the server offer."
            return True

        payment.status = "paid"
        payment.failure_code = None
        payment.failure_message = None
        payment.completed_at = payment.completed_at or utc_now_naive()
        existing = db.scalar(select(Entitlement).where(Entitlement.payment_id == payment.id))
        if existing is None:
            db.add(
                Entitlement(
                    owner_id=payment.owner_id,
                    payment_id=payment.id,
                    package_code=payment.package_code,
                    status="available",
                    revision_limit=FUNDING_READY.revision_limit,
                    revisions_used=0,
                )
            )
        return True

    def _fail_checkout(self, db: Session, obj: Any, code: str) -> bool:
        payment = self._checkout_payment(db, obj)
        if payment is None:
            return False
        if payment.status not in {"paid", "partially_refunded", "refunded"}:
            payment.status = "failed"
            payment.failure_code = code
            payment.failure_message = "Stripe reported that payment did not complete."
        return True

    def _abandon_checkout(self, db: Session, obj: Any) -> bool:
        payment = self._checkout_payment(db, obj)
        if payment is None:
            return False
        if payment.status in {"checkout_pending", "processing"}:
            payment.status = "abandoned"
        return True

    @staticmethod
    def _fail_payment_intent(db: Session, obj: Any) -> bool:
        from web_api.models import Payment

        intent_id = _provider_id(obj)
        payment = db.scalar(
            select(Payment).where(Payment.provider_payment_intent_id == intent_id)
        )
        if payment is None:
            return False
        if payment.status not in {"paid", "partially_refunded", "refunded"}:
            last_error = _value(obj, "last_payment_error", {})
            payment.status = "failed"
            payment.failure_code = str(_value(last_error, "code", "payment_failed"))[:64]
            payment.failure_message = str(
                _value(last_error, "message", "Stripe reported that payment failed.")
            )[:1000]
        return True

    @staticmethod
    def _record_refund(db: Session, obj: Any) -> bool:
        from web_api.models import Entitlement, Payment, Refund

        refund_id = _provider_id(obj)
        if refund_id is None:
            return False
        payment_intent_id = _provider_id(_value(obj, "payment_intent"))
        charge_id = _provider_id(_value(obj, "charge"))
        payment = None
        if payment_intent_id:
            payment = db.scalar(
                select(Payment).where(Payment.provider_payment_intent_id == payment_intent_id)
            )
        if payment is None and charge_id:
            payment = db.scalar(select(Payment).where(Payment.provider_charge_id == charge_id))
        if payment is None:
            return False
        if charge_id and payment.provider_charge_id is None:
            payment.provider_charge_id = charge_id

        refund = db.scalar(select(Refund).where(Refund.provider_refund_id == refund_id))
        if refund is None:
            refund = Refund(payment_id=payment.id, provider_refund_id=refund_id)
            db.add(refund)
        refund.status = str(_value(obj, "status", "pending"))[:24]
        refund.amount = int(_value(obj, "amount", 0))
        refund.currency = str(_value(obj, "currency", payment.currency)).lower()[:3]
        reason = _value(obj, "reason")
        refund.reason = str(reason)[:64] if reason else None
        db.flush()

        successful_total = db.scalar(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(
                Refund.payment_id == payment.id, Refund.status == "succeeded"
            )
        )
        if successful_total >= payment.amount_total:
            payment.status = "refunded"
            payment.refunded_at = utc_now_naive()
            entitlement = db.scalar(
                select(Entitlement).where(Entitlement.payment_id == payment.id)
            )
            if entitlement is not None and entitlement.status != "refunded":
                entitlement.status = "refunded"
                entitlement.reserved_run_id = None
                entitlement.refunded_at = utc_now_naive()
        elif successful_total > 0:
            payment.status = "partially_refunded"
        return True

    def create_support_request(
        self,
        *,
        owner_id: str,
        client_request_id: str,
        kind: str,
        message: str,
        payment_id: str | None,
        run_id: str | None,
    ):
        from web_api.models import Payment, Project, Run, SupportRequest

        with self.session_factory() as db:
            existing = db.scalar(
                select(SupportRequest).where(
                    SupportRequest.owner_id == owner_id,
                    SupportRequest.client_request_id == client_request_id,
                )
            )
            if existing is not None:
                db.expunge(existing)
                return existing
            if payment_id and db.scalar(
                select(Payment.id).where(Payment.id == payment_id, Payment.owner_id == owner_id)
            ) is None:
                raise LookupError("Payment not found")
            if run_id and db.scalar(
                select(Run.id)
                .join(Project, Project.id == Run.project_id)
                .where(Run.id == run_id, Project.owner_id == owner_id)
            ) is None:
                raise LookupError("Run not found")
            request = SupportRequest(
                owner_id=owner_id,
                client_request_id=client_request_id,
                kind=kind,
                status="open",
                payment_id=payment_id,
                run_id=run_id,
                message=message,
            )
            db.add(request)
            db.commit()
            db.refresh(request)
            db.expunge(request)
            return request

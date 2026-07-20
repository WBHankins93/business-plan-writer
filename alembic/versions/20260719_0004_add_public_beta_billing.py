"""add public beta payments, entitlements, refunds, and support

Revision ID: 20260719_0004
Revises: 20260719_0003
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260719_0004"
down_revision = "20260719_0003"
branch_labels = None
depends_on = None


def postgres_rls_statements() -> tuple[str, ...]:
    owner = "NULLIF(current_setting('app.current_user_id', true), '')"
    predicates = {
        "payments": f"owner_id = {owner}",
        "entitlements": f"owner_id = {owner}",
        "refunds": (
            "EXISTS (SELECT 1 FROM payments p "
            f"WHERE p.id = refunds.payment_id AND p.owner_id = {owner})"
        ),
        "support_requests": f"owner_id = {owner}",
    }
    statements = []
    for table, predicate in predicates.items():
        statements.extend(
            [
                f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                f"CREATE POLICY {table}_owner_all ON {table} FOR ALL "
                f"USING ({predicate}) WITH CHECK ({predicate})",
            ]
        )
    statements.append("REVOKE ALL ON webhook_events FROM PUBLIC")
    return tuple(statements)


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "owner_id",
            sa.String(length=36),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("package_code", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_total", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_livemode", sa.Boolean(), nullable=False),
        sa.Column("provider_checkout_session_id", sa.String(length=255), unique=True),
        sa.Column("provider_payment_intent_id", sa.String(length=255), unique=True),
        sa.Column("provider_charge_id", sa.String(length=255), unique=True),
        sa.Column("failure_code", sa.String(length=64)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("refunded_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('checkout_pending', 'processing', 'paid', 'failed', "
            "'abandoned', 'partially_refunded', 'refunded')",
            name="ck_payments_status",
        ),
    )
    op.create_index("ix_payments_owner_id", "payments", ["owner_id"])
    op.create_index("ix_payments_status", "payments", ["status"])

    op.create_table(
        "entitlements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "owner_id",
            sa.String(length=36),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("package_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reserved_run_id", sa.String(length=36)),
        sa.Column("revision_limit", sa.Integer(), nullable=False),
        sa.Column("revisions_used", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("refunded_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("payment_id", name="uq_entitlements_payment_id"),
        sa.CheckConstraint(
            "status IN ('available', 'reserved', 'consumed', 'refunded')",
            name="ck_entitlements_status",
        ),
        sa.CheckConstraint("revision_limit >= 0", name="ck_entitlements_revision_limit"),
        sa.CheckConstraint("revisions_used >= 0", name="ck_entitlements_revisions_used"),
    )
    op.create_index("ix_entitlements_owner_id", "entitlements", ["owner_id"])
    op.create_index("ix_entitlements_payment_id", "entitlements", ["payment_id"])
    op.create_index("ix_entitlements_status", "entitlements", ["status"])

    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("entitlement_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_runs_entitlement_id_entitlements",
            "entitlements",
            ["entitlement_id"],
            ["id"],
        )
        batch_op.create_index("ix_runs_entitlement_id", ["entitlement_id"])

    op.create_table(
        "webhook_events",
        sa.Column("provider_event_id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("provider_object_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime()),
    )
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])

    op.create_table(
        "refunds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_refund_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])
    op.create_index("ix_refunds_status", "refunds", ["status"])

    op.create_table(
        "support_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "owner_id",
            sa.String(length=36),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_request_id", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "run_id", sa.String(length=36), sa.ForeignKey("runs.id", ondelete="SET NULL")
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_id", "client_request_id", name="uq_support_owner_request"),
        sa.CheckConstraint(
            "kind IN ('payment', 'refund', 'generation', 'human_qa', 'other')",
            name="ck_support_requests_kind",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')",
            name="ck_support_requests_status",
        ),
    )
    op.create_index("ix_support_requests_owner_id", "support_requests", ["owner_id"])
    op.create_index("ix_support_requests_kind", "support_requests", ["kind"])
    op.create_index("ix_support_requests_status", "support_requests", ["status"])
    if op.get_bind().dialect.name == "postgresql":
        for statement in postgres_rls_statements():
            op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("support_requests", "refunds", "entitlements", "payments"):
            op.execute(f"DROP POLICY IF EXISTS {table}_owner_all ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_support_requests_status", table_name="support_requests")
    op.drop_index("ix_support_requests_kind", table_name="support_requests")
    op.drop_index("ix_support_requests_owner_id", table_name="support_requests")
    op.drop_table("support_requests")
    op.drop_index("ix_refunds_status", table_name="refunds")
    op.drop_index("ix_refunds_payment_id", table_name="refunds")
    op.drop_table("refunds")
    op.drop_index("ix_webhook_events_event_type", table_name="webhook_events")
    op.drop_table("webhook_events")
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_index("ix_runs_entitlement_id")
        batch_op.drop_constraint("fk_runs_entitlement_id_entitlements", type_="foreignkey")
        batch_op.drop_column("entitlement_id")
    op.drop_index("ix_entitlements_status", table_name="entitlements")
    op.drop_index("ix_entitlements_payment_id", table_name="entitlements")
    op.drop_index("ix_entitlements_owner_id", table_name="entitlements")
    op.drop_table("entitlements")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_owner_id", table_name="payments")
    op.drop_table("payments")

from __future__ import annotations

from dataclasses import dataclass

from web_api.config import funding_ready_currency, funding_ready_price_cents


@dataclass(frozen=True)
class PackageDefinition:
    code: str
    name: str
    description: str
    revision_limit: int
    turnaround: str
    deliverables: tuple[str, ...]
    human_qa: str

    @property
    def price_cents(self) -> int:
        return funding_ready_price_cents()

    @property
    def currency(self) -> str:
        return funding_ready_currency()

    def public_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "purchase_type": "one_time",
            "price": {"amount": self.price_cents, "currency": self.currency},
            "revision_limit": self.revision_limit,
            "turnaround": self.turnaround,
            "deliverables": list(self.deliverables),
            "human_qa": self.human_qa,
        }


FUNDING_READY = PackageDefinition(
    code="funding_ready_v1",
    name="Funding Ready business plan",
    description="One funding-ready business plan from one completed intake.",
    revision_limit=2,
    turnaround="Delivery targeted within two business days after a complete intake.",
    deliverables=("Funding-ready business plan", "DOCX export", "PDF export"),
    human_qa="Optional by support request during the public beta.",
)

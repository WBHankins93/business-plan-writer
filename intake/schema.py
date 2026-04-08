"""
intake/schema.py
Business plan intake schema — field definitions, tier classifications, and validation.

Tier 1 (Critical):  Required for the document core. Missing = must infer or flag.
Tier 2 (Structural): Section-specific. Thin answers trigger follow-up questions.
Tier 3 (Enhancement): Optional. Missing = [WRITER_NOTE] in output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re

# Vague answers that count as "thin" regardless of length
_VAGUE_PHRASES = {
    "tbd", "n/a", "na", "not sure", "not applicable", "unknown",
    "to be determined", "to be decided", "will figure out", "haven't decided",
    "don't know", "not yet", "later", "soon", "eventually",
}

# Minimum character threshold for a non-thin answer
_MIN_CHARS: dict[int, int] = {
    1: 10,   # Tier 1 — very short answers still accepted (e.g., a business name)
    2: 40,   # Tier 2 — needs substantive content
    3: 20,   # Tier 3 — nice-to-have detail
}


@dataclass
class FieldDef:
    section: str
    name: str
    tier: int          # 1 = Critical, 2 = Structural, 3 = Enhancement
    label: str         # Human-readable label for reports
    description: str   # What this field captures


# ── Schema definition ──────────────────────────────────────────────────────────

SCHEMA: list[FieldDef] = [
    # ── Section 1: Business Information ──────────────────────────────────────
    FieldDef("business_information", "business_name", 1, "Business Name",
             "The legal or operating name of the business."),
    FieldDef("business_information", "owner_name", 1, "Owner Name",
             "Full name of the primary business owner."),
    FieldDef("business_information", "ownership_structure", 1, "Ownership Structure",
             "Legal structure: LLC, Sole Proprietorship, S-Corp, etc."),
    FieldDef("business_information", "industry", 1, "Industry",
             "The industry or sector the business operates in."),
    FieldDef("business_information", "business_stage", 2, "Business Stage",
             "Startup, early-stage, established, expansion, etc."),
    FieldDef("business_information", "funding_purpose", 2, "Funding Purpose",
             "What the plan is for — lender, investor, grant, internal planning."),
    FieldDef("business_information", "funding_amount", 2, "Funding Amount Sought",
             "Dollar amount being sought, if applicable."),
    FieldDef("business_information", "location", 2, "Business Location",
             "City, state, and/or address of operations."),
    FieldDef("business_information", "year_founded", 3, "Year Founded",
             "When the business was or will be founded."),

    # ── Section 2: Management Details ────────────────────────────────────────
    FieldDef("management_details", "owner_background", 1, "Owner Background",
             "Professional history, credentials, and relevant experience."),
    FieldDef("management_details", "management_team", 2, "Management Team",
             "Key team members, their roles, and relevant qualifications."),
    FieldDef("management_details", "hiring_plans", 2, "Hiring Plans",
             "Planned hires, roles, and timeline for building the team."),
    FieldDef("management_details", "advisors", 3, "Advisors / Board",
             "Mentors, advisors, or board members supporting the business."),

    # ── Section 3: Product / Service Summary ─────────────────────────────────
    FieldDef("product_service_summary", "services_offered", 1, "Services / Products",
             "What the business sells or provides — clear, specific description."),
    FieldDef("product_service_summary", "service_delivery", 2, "Service Delivery Method",
             "How services are delivered: in-person, telehealth, online, etc."),
    FieldDef("product_service_summary", "pricing_structure", 2, "Pricing Structure",
             "How the business charges — rates, packages, session fees, etc."),
    FieldDef("product_service_summary", "future_offerings", 3, "Future Offerings",
             "Planned additions to the product or service line."),
    FieldDef("product_service_summary", "differentiators", 2, "Key Differentiators",
             "What makes this offering meaningfully different from alternatives."),

    # ── Section 4: Sales Strategy ─────────────────────────────────────────────
    FieldDef("sales_strategy", "sales_process", 2, "Sales Process",
             "How a prospect becomes a paying client — lead to close."),
    FieldDef("sales_strategy", "payment_terms", 2, "Payment Terms",
             "How clients pay: insurance, out-of-pocket, invoicing, deposits, etc."),
    FieldDef("sales_strategy", "retention_strategy", 2, "Client Retention Strategy",
             "How the business keeps clients and encourages repeat business."),
    FieldDef("sales_strategy", "referral_sources", 2, "Referral Sources",
             "Who or what channels drive new clients to the business."),

    # ── Section 5: Market Analysis ────────────────────────────────────────────
    FieldDef("market_analysis", "geographic_market", 1, "Geographic Market",
             "Where the business operates and serves clients."),
    FieldDef("market_analysis", "target_customer", 1, "Target Customer Profile",
             "Who the ideal client is — demographics, needs, behaviors."),
    FieldDef("market_analysis", "market_size", 2, "Market Size / Opportunity",
             "Estimated size of the addressable market."),
    FieldDef("market_analysis", "industry_state", 2, "Industry State",
             "Current trends, growth rate, and dynamics in the industry."),
    FieldDef("market_analysis", "customer_pain_points", 2, "Customer Pain Points",
             "The core problems the target customer experiences."),

    # ── Section 6: Advertising Strategy ──────────────────────────────────────
    FieldDef("advertising_strategy", "initial_marketing", 1, "Initial Marketing Channels",
             "How the business will reach its first clients."),
    FieldDef("advertising_strategy", "marketing_budget", 2, "Marketing Budget",
             "Monthly or annual marketing spend."),
    FieldDef("advertising_strategy", "expansion_marketing", 3, "Long-Term Marketing Plans",
             "How marketing strategy evolves as the business grows."),
    FieldDef("advertising_strategy", "digital_presence", 2, "Digital Presence",
             "Website, social media, SEO, or other online channels."),

    # ── Section 7: Competition ────────────────────────────────────────────────
    FieldDef("competition", "main_competitors", 1, "Main Competitors",
             "Named competitors or types of competing businesses."),
    FieldDef("competition", "competitive_edge", 1, "Competitive Advantage",
             "Why clients choose this business over alternatives."),
    FieldDef("competition", "market_gaps", 2, "Market Gaps",
             "Unmet needs or underserved segments this business addresses."),

    # ── Section 8: Strategy and Implementation ────────────────────────────────
    FieldDef("strategy_and_implementation", "business_strategy", 1, "Business Strategy",
             "The overall strategic approach to building and growing the business."),
    FieldDef("strategy_and_implementation", "near_term_priorities", 2, "Near-Term Priorities",
             "The 3-5 most important things to accomplish in the next 90 days."),
    FieldDef("strategy_and_implementation", "key_risks", 2, "Key Risks",
             "The main risks facing the business and how they are addressed."),
    FieldDef("strategy_and_implementation", "partnerships", 3, "Key Partnerships",
             "Strategic partners, vendors, or relationships critical to the business."),

    # ── Section 9: Milestones ─────────────────────────────────────────────────
    FieldDef("milestones", "twelve_month_goals", 1, "12-Month Goals",
             "Specific targets to hit in the first year of operation."),
    FieldDef("milestones", "twenty_four_month_goals", 2, "24-Month Goals",
             "Where the business should be in two years."),
    FieldDef("milestones", "key_metrics", 2, "Key Success Metrics",
             "How the business measures progress (revenue, clients, utilization, etc.)."),

    # ── Section 10: Financial Information ─────────────────────────────────────
    FieldDef("financial_information", "cash_flow_narrative", 1, "Cash Flow Narrative",
             "Description of how cash flows in and out of the business."),
    FieldDef("financial_information", "financial_plan_summary", 1, "Financial Plan Summary",
             "High-level description of the financial approach and assumptions."),
    FieldDef("financial_information", "break_even_point", 2, "Break-Even Point",
             "When and at what revenue level the business becomes profitable."),

    # ── Section 11: Income ────────────────────────────────────────────────────
    FieldDef("income", "beginning_balance", 1, "Beginning Balance / Startup Capital",
             "Cash on hand or capital available at launch."),
    FieldDef("income", "client_volume", 1, "Client Volume Projections",
             "Expected number of clients per week/month at various stages."),
    FieldDef("income", "monthly_revenue_projection", 1, "Monthly Revenue Projection",
             "Projected monthly revenue by month or phase."),
    FieldDef("income", "annual_revenue_projection", 2, "Annual Revenue Projection",
             "Year 1 and Year 2 projected revenue totals."),
    FieldDef("income", "revenue_sources", 2, "Revenue Sources",
             "Breakdown of income by service line, payer type, or channel."),

    # ── Section 12: Expenses ──────────────────────────────────────────────────
    FieldDef("expenses", "payroll", 2, "Payroll",
             "Owner draw, employee wages, and contractor costs."),
    FieldDef("expenses", "rent_utilities", 2, "Rent / Utilities",
             "Monthly office, clinic, or workspace costs."),
    FieldDef("expenses", "cogs", 2, "Cost of Goods / Direct Costs",
             "Direct costs tied to service delivery."),
    FieldDef("expenses", "advertising_expense", 2, "Advertising Expense",
             "Monthly marketing and advertising spend."),
    FieldDef("expenses", "other_operating", 2, "Other Operating Expenses",
             "Software, insurance, licensing, professional fees, supplies, etc."),
    FieldDef("expenses", "taxes", 2, "Taxes",
             "Estimated tax obligations (self-employment, income, payroll)."),
    FieldDef("expenses", "loans_debt_service", 3, "Loans / Debt Service",
             "Monthly payments on any loans or financing."),
    FieldDef("expenses", "capital_assets", 3, "Capital Assets / Equipment",
             "One-time equipment or asset purchases planned."),
]

# ── Lookup helpers ─────────────────────────────────────────────────────────────

def fields_by_section() -> dict[str, list[FieldDef]]:
    """Return schema grouped by section name."""
    result: dict[str, list[FieldDef]] = {}
    for f in SCHEMA:
        result.setdefault(f.section, []).append(f)
    return result


def field_by_name(name: str) -> FieldDef | None:
    for f in SCHEMA:
        if f.name == name:
            return f
    return None


# ── Validation ─────────────────────────────────────────────────────────────────

def is_thin(value: Any, tier: int) -> bool:
    """Return True if the value is missing or too thin for its tier."""
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    if text.lower() in _VAGUE_PHRASES:
        return True
    return len(text) < _MIN_CHARS.get(tier, 20)


@dataclass
class FieldResult:
    field: FieldDef
    value: Any
    present: bool
    thin: bool
    note: str = ""       # [WRITER_NOTE] marker for Tier 3 if missing


@dataclass
class ValidationReport:
    field_results: list[FieldResult] = field(default_factory=list)
    typed_issues: list[str] = field(default_factory=list)
    cross_field_issues: list[str] = field(default_factory=list)

    @property
    def missing_tier1(self) -> list[FieldResult]:
        return [r for r in self.field_results if r.field.tier == 1 and not r.present]

    @property
    def thin_tier2(self) -> list[FieldResult]:
        return [r for r in self.field_results if r.field.tier == 2 and r.thin]

    @property
    def missing_tier3(self) -> list[FieldResult]:
        return [r for r in self.field_results if r.field.tier == 3 and not r.present]

    @property
    def completeness_score(self) -> int:
        """0-100: percent of Tier 1 + Tier 2 fields with non-thin answers."""
        tier12 = [r for r in self.field_results if r.field.tier in (1, 2)]
        if not tier12:
            return 0
        good = sum(1 for r in tier12 if not r.thin)
        return round(good / len(tier12) * 100)

    def summary(self) -> str:
        lines = [f"Completeness score: {self.completeness_score}/100"]
        if self.missing_tier1:
            lines.append(f"Missing Tier 1 (critical): {[r.field.name for r in self.missing_tier1]}")
        if self.thin_tier2:
            lines.append(f"Thin Tier 2 (structural): {[r.field.name for r in self.thin_tier2]}")
        if self.missing_tier3:
            lines.append(f"Missing Tier 3 (enhancement): {[r.field.name for r in self.missing_tier3]}")
        if self.typed_issues:
            lines.append(f"Typed validation issues: {self.typed_issues}")
        if self.cross_field_issues:
            lines.append(f"Cross-field issues: {self.cross_field_issues}")
        return "\n".join(lines)


_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def _to_float(value: Any) -> float | None:
    """Best-effort numeric parser for intake fields that may include currency symbols."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return None
    match = _NUMBER_RE.search(text.replace("$", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def validate_intake(intake: dict[str, Any]) -> tuple[dict[str, Any], ValidationReport]:
    """
    Validate an intake dict against the schema.

    Returns:
        (annotated_intake, report) where annotated_intake has [WRITER_NOTE] tags
        appended to thin/missing Tier 3 fields.
    """
    report = ValidationReport()
    annotated = dict(intake)  # shallow copy

    for field_def in SCHEMA:
        section_data = intake.get(field_def.section, {})
        value = section_data.get(field_def.name) if isinstance(section_data, dict) else None
        present = value is not None and str(value).strip() != ""
        thin = is_thin(value, field_def.tier)

        note = ""
        if field_def.tier == 3 and (not present or thin):
            note = "[WRITER_NOTE: not provided — enhance if possible]"

        report.field_results.append(FieldResult(
            field=field_def,
            value=value,
            present=present,
            thin=thin,
            note=note,
        ))

    _run_typed_validation(intake, report)
    _run_cross_field_validation(intake, report)

    return annotated, report


def _run_typed_validation(intake: dict[str, Any], report: ValidationReport) -> None:
    business = intake.get("business_information", {})
    advertising = intake.get("advertising_strategy", {})
    income = intake.get("income", {})
    expenses = intake.get("expenses", {})

    typed_fields = [
        ("business_information.funding_amount", business.get("funding_amount")),
        ("advertising_strategy.marketing_budget", advertising.get("marketing_budget")),
        ("income.beginning_balance", income.get("beginning_balance")),
        ("income.monthly_revenue_projection", income.get("monthly_revenue_projection")),
        ("income.annual_revenue_projection", income.get("annual_revenue_projection")),
        ("expenses.payroll", expenses.get("payroll")),
        ("expenses.rent_utilities", expenses.get("rent_utilities")),
        ("expenses.advertising_expense", expenses.get("advertising_expense")),
        ("expenses.taxes", expenses.get("taxes")),
    ]

    for field_path, raw in typed_fields:
        if raw is None or str(raw).strip() == "":
            continue
        if _to_float(raw) is None:
            report.typed_issues.append(
                f"{field_path} should include a parseable numeric value."
            )


def _run_cross_field_validation(intake: dict[str, Any], report: ValidationReport) -> None:
    income = intake.get("income", {})
    monthly = _to_float(income.get("monthly_revenue_projection"))
    annual = _to_float(income.get("annual_revenue_projection"))

    if monthly is not None and annual is not None:
        projected_annual = monthly * 12
        # 20% tolerance to account for ramp assumptions in free-form input
        if annual and abs(projected_annual - annual) / annual > 0.20:
            report.cross_field_issues.append(
                "income.monthly_revenue_projection and income.annual_revenue_projection appear inconsistent (>20% delta)."
            )

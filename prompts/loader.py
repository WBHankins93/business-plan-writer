"""
prompts/loader.py
-----------------
Builds layered system prompt identities for each agent by composing:

    foundation.md → response-standards.md → persona(s)

All files are read from the local prompts/library/ directory.
No network calls at runtime. Run scripts/sync_prompts.py separately
to pull updates from GitHub.

Usage
-----
    from prompts.loader import build_agent_identity, AGENT_PERSONAS

    # Standard agent
    identity = build_agent_identity(AGENT_PERSONAS["agent_3"])

    # Agent 4 — standard (non-tech client)
    identity = build_agent_identity(AGENT_PERSONAS["agent_4"])

    # Agent 4 — SaaS/tech client
    identity = build_agent_identity(AGENT_PERSONAS["agent_4_saas"])

    # Append task-specific instructions
    system_prompt = identity + "\\n\\n---\\n\\n" + task_instructions
"""

from pathlib import Path
from functools import lru_cache

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LIBRARY_ROOT = Path(__file__).parent / "library"

FOUNDATION_PATH = LIBRARY_ROOT / "00_foundation" / "foundation.md"
STANDARDS_PATH  = LIBRARY_ROOT / "01_response-standards" / "response-standards.md"

# Persona file paths relative to LIBRARY_ROOT
PERSONA_FILES = {
    # Advisory
    "decision_anchor":  "02_personas/advisory/decision-anchor.md",
    "finance_dragon":   "02_personas/advisory/finance-dragon.md",
    "pattern_seer":     "02_personas/advisory/pattern-seer.md",
    "red_team":         "02_personas/advisory/red-team.md",

    # Business
    "builder_refiner":          "02_personas/business/builder-refiner.md",
    "business_plan_architect":  "02_personas/business/business-plan-architect.md",
    "saas_founder":             "02_personas/business/saas-founder.md",
}

# ---------------------------------------------------------------------------
# Agent → Persona mapping
# ---------------------------------------------------------------------------
# Each agent key maps to a list of persona keys loaded in order.
# Empty list = foundation + standards only (no persona).
#
# Agent 1  — Validator          — Decision Anchor
#             Closes contradiction loops instead of asking open-ended questions.
#
# Agent 2  — Market Builder     — Pattern Seer
#             Produces market intelligence, not just market information.
#
# Agent 3  — Financial Checker  — Finance Dragon
#             Skeptical financial validation; calls out weak projections.
#
# Agent 4  — Plan Writer        — Business Plan Architect (base)
#             SaaS Founder added conditionally for tech/software clients.
#
# Agent 5  — Critic             — Red Team + Builder-Refiner (in order)
#             Red Team finds problems; Builder-Refiner filters to what ships.

AGENT_PERSONAS = {
    "agent_1":         ["decision_anchor"],
    "agent_2":         ["pattern_seer"],
    "agent_3":         ["finance_dragon"],
    "agent_4":         ["business_plan_architect"],
    "agent_4_saas":    ["business_plan_architect", "saas_founder"],
    "agent_5":         ["red_team", "builder_refiner"],
}

# ---------------------------------------------------------------------------
# Industry keywords that trigger SaaS Founder enrichment for Agent 4
# ---------------------------------------------------------------------------

SAAS_TRIGGER_KEYWORDS = [
    "saas", "software", "app", "application", "platform", "marketplace",
    "subscription software", "web app", "mobile app", "api", "tech startup",
    "software as a service", "cloud", "plugin", "tool", "dashboard",
]

# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _read(path: Path) -> str:
    """Read a file, return empty string with warning if missing."""
    if not path.exists():
        print(
            f"  [loader] WARNING: file not found — {path}\n"
            f"  Run: python scripts/sync_prompts.py"
        )
        return ""
    return path.read_text(encoding="utf-8")


def build_agent_identity(personas: list[str] | None = None) -> str:
    """
    Assembles foundation → response-standards → persona(s) in order.

    Parameters
    ----------
    personas : list of persona keys from PERSONA_FILES, or None
        Pass None or empty list for foundation + standards only.

    Returns
    -------
    str
        Complete layered identity string, ready to prepend to task instructions.
    """
    parts = []

    foundation = _read(FOUNDATION_PATH)
    if foundation:
        parts.append(foundation)

    standards = _read(STANDARDS_PATH)
    if standards:
        parts.append(standards)

    for key in (personas or []):
        if key not in PERSONA_FILES:
            print(f"  [loader] WARNING: unknown persona key '{key}' — skipping")
            continue
        content = _read(LIBRARY_ROOT / PERSONA_FILES[key])
        if content:
            parts.append(content)

    return "\n\n---\n\n".join(parts)


def build_agent_identity_for(agent_key: str) -> str:
    """
    Convenience wrapper. Pass an agent key from AGENT_PERSONAS.

    Example
    -------
        identity = build_agent_identity_for("agent_3")
    """
    if agent_key not in AGENT_PERSONAS:
        raise ValueError(
            f"Unknown agent key '{agent_key}'. "
            f"Valid keys: {list(AGENT_PERSONAS.keys())}"
        )
    return build_agent_identity(AGENT_PERSONAS[agent_key])


def resolve_agent_4_key(industry: str) -> str:
    """
    Determines whether Agent 4 should use the standard or SaaS-enriched
    identity based on the industry field from the intake.

    Returns 'agent_4_saas' if the industry matches a SaaS trigger keyword,
    otherwise returns 'agent_4'.

    Parameters
    ----------
    industry : str
        Raw industry text from intake['business_information']['industry']

    Example
    -------
        key = resolve_agent_4_key("B2B SaaS platform for logistics")
        identity = build_agent_identity_for(key)
    """
    industry_lower = industry.lower()
    for keyword in SAAS_TRIGGER_KEYWORDS:
        if keyword in industry_lower:
            return "agent_4_saas"
    return "agent_4"


# ---------------------------------------------------------------------------
# Validation — run directly to verify all files are present
# ---------------------------------------------------------------------------

def validate_library() -> bool:
    """
    Checks that all required library files exist locally.
    Returns True if all files are present, False otherwise.
    Call this from main.py at startup.

    Example
    -------
        from prompts.loader import validate_library
        if not validate_library():
            sys.exit(1)
    """
    required = [FOUNDATION_PATH, STANDARDS_PATH]
    for rel_path in PERSONA_FILES.values():
        required.append(LIBRARY_ROOT / rel_path)

    missing = [p for p in required if not p.exists()]

    if missing:
        print()
        print("  [loader] Missing prompt library files:")
        for p in missing:
            print(f"    ✗ {p.relative_to(LIBRARY_ROOT.parent)}")
        print()
        print("  Run: python scripts/sync_prompts.py")
        print()
        return False

    print("  [loader] ✓ All prompt library files present")
    return True


# ---------------------------------------------------------------------------
# CLI — python prompts/loader.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print()
    print("Prompt Library — Validation")
    print("-" * 40)

    ok = validate_library()

    if ok and len(sys.argv) > 1:
        # Preview mode: python prompts/loader.py agent_3
        agent_key = sys.argv[1]
        print()
        print(f"Preview identity for: {agent_key}")
        print("-" * 40)
        try:
            identity = build_agent_identity_for(agent_key)
            # Show first 500 chars as a sanity check
            preview = identity[:500].replace("\n", " ↵ ")
            print(f"{preview}...")
            print()
            print(f"Total identity length: {len(identity)} characters")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    sys.exit(0 if ok else 1)

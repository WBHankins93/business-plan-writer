#!/usr/bin/env python3
"""
sync_prompts.py
---------------
Manually syncs prompt library files from GitHub into the local
prompts/library/ directory. Run this intentionally when you want
to pull updates from your prompt-library repo into the business
plan writer. Never called by the application at runtime.

Usage:
    python scripts/sync_prompts.py              # Sync all files
    python scripts/sync_prompts.py --dry-run    # Preview changes without writing
    python scripts/sync_prompts.py --force      # Overwrite without diff prompt
"""

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/WBHankins93/prompt-library/main"
)

# Local destination (relative to project root)
LOCAL_LIBRARY_ROOT = Path(__file__).parent.parent / "prompts" / "library"

# Exact files to sync — path relative to repo root on GitHub
# and relative to LOCAL_LIBRARY_ROOT locally.
# Format: (github_path, local_path)
FILES_TO_SYNC = [
    # Foundation
    (
        "00_foundation/foundation.md",
        "00_foundation/foundation.md",
    ),
    # Response standards
    (
        "01_response-standards/response-standards.md",
        "01_response-standards/response-standards.md",
    ),
    # Advisory personas
    (
        "02_personas/advisory/decision-anchor.md",
        "02_personas/advisory/decision-anchor.md",
    ),
    (
        "02_personas/advisory/startup-operator.md",
        "02_personas/advisory/startup-operator.md",
    ),
    (
        "02_personas/advisory/finance-dragon.md",
        "02_personas/advisory/finance-dragon.md",
    ),
    (
        "02_personas/advisory/financial-analyst.md",
        "02_personas/advisory/financial-analyst.md",
    ),
    (
        "02_personas/advisory/pattern-seer.md",
        "02_personas/advisory/pattern-seer.md",
    ),
    (
        "02_personas/advisory/gtm-strategist.md",
        "02_personas/advisory/gtm-strategist.md",
    ),
    (
        "02_personas/advisory/red-team.md",
        "02_personas/advisory/red-team.md",
    ),
    (
        "02_personas/advisory/vc-partner.md",
        "02_personas/advisory/vc-partner.md",
    ),
    # Business personas
    (
        "02_personas/business/builder-refiner.md",
        "02_personas/business/builder-refiner.md",
    ),
    (
        "02_personas/business/saas-founder.md",
        "02_personas/business/saas-founder.md",
    ),
    # Business Plan Architect — written specifically for this product.
    # Add this file to your prompt-library repo, then it syncs automatically.
    (
        "02_personas/business/business-plan-architect.md",
        "02_personas/business/business-plan-architect.md",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_remote(github_path: str) -> str | None:
    """Fetch raw file content from GitHub. Returns None on failure."""
    try:
        import urllib.request
        url = f"{GITHUB_RAW_BASE}/{github_path}"
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"  ERROR fetching {github_path}: {e}")
        return None


def read_local(local_path: Path) -> str | None:
    """Read existing local file. Returns None if it doesn't exist."""
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")
    return None


def diff_summary(old: str | None, new: str) -> str:
    """Return a one-line summary of the change."""
    if old is None:
        return "NEW FILE"
    if old == new:
        return "UNCHANGED"
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    added = len(new_lines) - len(old_lines)
    sign = "+" if added >= 0 else ""
    return f"CHANGED  ({sign}{added} lines)"


def confirm(prompt: str) -> bool:
    """Simple y/n confirmation."""
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync prompt library files from GitHub into prompts/library/"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing any files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite all changed files without confirmation",
    )
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  Prompt Library Sync")
    print(f"  Source : {GITHUB_RAW_BASE}")
    print(f"  Target : {LOCAL_LIBRARY_ROOT}")
    if args.dry_run:
        print("  Mode   : DRY RUN — no files will be written")
    elif args.force:
        print("  Mode   : FORCE — all changes overwritten without prompting")
    else:
        print("  Mode   : INTERACTIVE — confirm each change")
    print("=" * 60)
    print()

    results = {"new": 0, "updated": 0, "unchanged": 0, "failed": 0, "skipped": 0}

    for github_path, local_rel_path in FILES_TO_SYNC:
        local_path = LOCAL_LIBRARY_ROOT / local_rel_path
        print(f"  {local_rel_path}")

        # Fetch remote
        remote_content = fetch_remote(github_path)
        if remote_content is None:
            print(f"    ✗ Failed to fetch — skipping")
            results["failed"] += 1
            continue

        # Compare with local
        local_content = read_local(local_path)
        status = diff_summary(local_content, remote_content)
        print(f"    → {status}")

        if status == "UNCHANGED":
            results["unchanged"] += 1
            continue

        if args.dry_run:
            if status == "NEW FILE":
                results["new"] += 1
            else:
                results["updated"] += 1
            continue

        # Confirm if needed
        if not args.force:
            should_write = confirm("    Write this file?")
            if not should_write:
                print("    Skipped.")
                results["skipped"] += 1
                continue

        # Write file
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(remote_content, encoding="utf-8")
        print("    ✓ Written")

        if status == "NEW FILE":
            results["new"] += 1
        else:
            results["updated"] += 1

    # Summary
    print()
    print("=" * 60)
    print("  Sync complete")
    print(f"  New      : {results['new']}")
    print(f"  Updated  : {results['updated']}")
    print(f"  Unchanged: {results['unchanged']}")
    print(f"  Skipped  : {results['skipped']}")
    print(f"  Failed   : {results['failed']}")
    print("=" * 60)
    print()

    if results["failed"] > 0:
        print(
            "  Some files failed to fetch. Check your internet connection\n"
            "  and verify the file paths exist in your GitHub repo.\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

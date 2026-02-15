#!/usr/bin/env python3
"""Validate documentation structure and cross-references.

Checks:
1. All files listed in CLAUDE.md Documentation Map exist
2. CLAUDE.md is under 200 lines
3. Each docs/ file has a # Title header
4. Internal cross-references (docs/foo.md) point to existing files
5. Doc freshness (last-verified comment not older than 60 days)
6. quality.md staleness (new test files not referenced)
"""

import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
DOCS_DIR = ROOT / "docs"
TESTS_DIR = ROOT / "tests"
QUALITY_MD = DOCS_DIR / "quality.md"
MAX_CLAUDE_LINES = 200
FRESHNESS_DAYS = 60

errors: list[str] = []
warnings: list[str] = []


def check_claude_md_size():
    """Check CLAUDE.md is under MAX_CLAUDE_LINES lines."""
    lines = CLAUDE_MD.read_text().splitlines()
    if len(lines) > MAX_CLAUDE_LINES:
        errors.append(
            f"CLAUDE.md is {len(lines)} lines (max {MAX_CLAUDE_LINES}). "
            f"FIX: Move detailed content to docs/ files — see docs/conventions.md"
        )


def check_documentation_map():
    """Check all files in the Documentation Map table exist."""
    content = CLAUDE_MD.read_text()
    # Match markdown table rows like: | `docs/foo.md` | description |
    pattern = re.compile(r"\|\s*`(docs/\S+)`\s*\|")
    for match in pattern.finditer(content):
        doc_path = ROOT / match.group(1)
        if not doc_path.exists():
            errors.append(
                f"Documentation Map references '{match.group(1)}' but file does not exist. "
                f"FIX: Create the file or remove it from the Documentation Map in CLAUDE.md"
            )


def check_doc_headers():
    """Check each docs/ markdown file has a # Title header."""
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        content = md_file.read_text().strip()
        if not content.startswith("# "):
            errors.append(
                f"{md_file.relative_to(ROOT)} is missing a '# Title' header. "
                f"FIX: Add a title as the first line of the file"
            )


def check_cross_references():
    """Check internal cross-references in all docs/ and CLAUDE.md files."""
    files_to_check = [CLAUDE_MD] + list(DOCS_DIR.glob("*.md"))
    pattern = re.compile(r"`(docs/\S+\.md)`|See\s+`(docs/\S+\.md)`")

    for filepath in files_to_check:
        content = filepath.read_text()
        for match in pattern.finditer(content):
            ref = match.group(1) or match.group(2)
            target = ROOT / ref
            if not target.exists():
                errors.append(
                    f"{filepath.relative_to(ROOT)} references '{ref}' but file does not exist. "
                    f"FIX: Create the file or fix the reference"
                )


def check_doc_freshness():
    """Check docs have a last-verified comment that isn't too old."""
    pattern = re.compile(r"<!--\s*last-verified:\s*(\d{4}-\d{2}-\d{2})\s*-->")
    threshold = date.today() - timedelta(days=FRESHNESS_DAYS)

    for md_file in sorted(DOCS_DIR.glob("*.md")):
        content = md_file.read_text()
        match = pattern.search(content)
        rel_path = md_file.relative_to(ROOT)

        if not match:
            warnings.append(
                f"{rel_path}: Missing '<!-- last-verified: YYYY-MM-DD -->' comment. "
                f"FIX: Add freshness comment after verifying content is accurate"
            )
            continue

        try:
            verified_date = date.fromisoformat(match.group(1))
            if verified_date < threshold:
                days_ago = (date.today() - verified_date).days
                warnings.append(
                    f"{rel_path}: Last verified {days_ago} days ago ({match.group(1)}). "
                    f"FIX: Re-verify content is accurate and update the date"
                )
        except ValueError:
            warnings.append(
                f"{rel_path}: Invalid date in last-verified comment: '{match.group(1)}'. "
                f"FIX: Use YYYY-MM-DD format"
            )


def check_quality_staleness():
    """Check if quality.md might be outdated based on test file counts."""
    if not QUALITY_MD.exists():
        return

    quality_content = QUALITY_MD.read_text()

    # Collect test files from known test directories
    test_files: set[str] = set()
    for test_dir in [TESTS_DIR / "evals", TESTS_DIR / "test_onboarding"]:
        if test_dir.exists():
            for f in test_dir.rglob("test_*.py"):
                test_files.add(f.name)

    # Also check for standalone test files in tests/
    if TESTS_DIR.exists():
        for f in TESTS_DIR.glob("test_*.py"):
            test_files.add(f.name)

    # Check if any test files aren't mentioned in quality.md
    unreferenced = [f for f in sorted(test_files) if f not in quality_content]
    if unreferenced:
        warnings.append(
            f"docs/quality.md may be outdated — {len(unreferenced)} test file(s) not referenced: "
            f"{', '.join(unreferenced[:5])}. "
            f"FIX: Review and update domain/layer grades in quality.md"
        )


def main():
    print("Validating documentation structure...")

    check_claude_md_size()
    check_documentation_map()
    check_doc_headers()
    check_cross_references()
    check_doc_freshness()
    check_quality_staleness()

    if warnings:
        print(f"\n{len(warnings)} warning(s):\n")
        for warning in warnings:
            print(f"  WARN: {warning}")

    if errors:
        print(f"\n{len(errors)} error(s) found:\n")
        for error in errors:
            print(f"  ERROR: {error}")
        sys.exit(1)
    else:
        if not warnings:
            print("All documentation checks passed.")
        else:
            print("\nNo errors (warnings are non-blocking).")
        sys.exit(0)


if __name__ == "__main__":
    main()

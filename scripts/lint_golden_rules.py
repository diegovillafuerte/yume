#!/usr/bin/env python3
"""Golden rules linter for Parlo codebase.

Enforces critical architectural invariants with agent-readable error messages.
Each rule outputs pass/fail with file:line and fix instructions.
Exit code 1 on any failure.

Rules:
1. No raw SQL in services
2. File size limit (2000 lines)
3. Import layering (services must not import from api)
4. Simulation layer protected
5. Traced services (key service files have @traced)
6. Organization scoping (queries on org-scoped models must filter by organization_id)
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
SERVICES_DIR = APP_DIR / "services"

errors: list[str] = []


# --- Rule 1: No raw SQL in services ---


def check_no_raw_sql():
    """Service files should not use raw SQL via text() or string queries."""
    for py_file in sorted(SERVICES_DIR.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            # Check for sqlalchemy text() usage
            if re.search(r"\btext\s*\(", line) and "from sqlalchemy" not in line:
                # Verify it's actually sqlalchemy text, not some other text()
                if "import" not in line and "#" not in line.split("text(")[0]:
                    errors.append(
                        f"{py_file.relative_to(ROOT)}:{i}: Raw SQL via text() detected. "
                        f"FIX: Use SQLAlchemy ORM queries instead of raw SQL"
                    )


# --- Rule 2: File size limit ---


def check_file_size():
    """No single Python file should exceed 2000 lines."""
    max_lines = 2000
    for py_file in sorted(APP_DIR.rglob("*.py")):
        lines = len(py_file.read_text().splitlines())
        if lines > max_lines:
            errors.append(
                f"{py_file.relative_to(ROOT)}: {lines} lines (max {max_lines}). "
                f"FIX: Split into smaller modules — see docs/conventions.md#file-size"
            )


# --- Rule 3: Import layering ---


def check_import_layering():
    """app/services/ should not import from app/api/."""
    for py_file in sorted(SERVICES_DIR.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r"from\s+app\.api", stripped) or re.search(r"import\s+app\.api", stripped):
                errors.append(
                    f"{py_file.relative_to(ROOT)}:{i}: Service imports from API layer. "
                    f"FIX: Services must not depend on API layer — see docs/architecture.md#layering"
                )


# --- Rule 4: Simulation layer protected ---


def check_simulation_protected():
    """simulate.py must exist and import MessageRouter."""
    simulate_path = APP_DIR / "api" / "v1" / "simulate.py"
    if not simulate_path.exists():
        errors.append(
            "app/api/v1/simulate.py does not exist. "
            "FIX: Simulation layer must stay functional — see docs/testing.md"
        )
        return

    content = simulate_path.read_text()
    if "MessageRouter" not in content:
        errors.append(
            "app/api/v1/simulate.py does not reference MessageRouter. "
            "FIX: Simulation must use the real MessageRouter — see docs/testing.md"
        )


# --- Rule 5: Traced services ---

KEY_SERVICE_FILES = [
    "message_router.py",
    "conversation.py",
    "onboarding.py",
    "customer_flows.py",
    "handoff.py",
    "staff_onboarding.py",
    "scheduling.py",
]


def check_traced_services():
    """Key service files should import and use @traced decorator."""
    for filename in KEY_SERVICE_FILES:
        filepath = SERVICES_DIR / filename
        if not filepath.exists():
            continue
        content = filepath.read_text()
        if "@traced" not in content:
            errors.append(
                f"app/services/{filename}: Missing @traced decorator usage. "
                f"FIX: Add @traced decorator to public functions — see docs/conventions.md#observability"
            )


# --- Rule 6: Organization scoping ---

# Models that have an organization_id column and must be filtered by it
ORG_SCOPED_MODELS = {
    "Appointment",
    "EndCustomer",
    "Location",
    "ParloUser",
    "ServiceType",
    "Conversation",
    "CustomerFlowSession",
    "StaffOnboardingSession",
    "AuthToken",
    "Staff",  # Alias for ParloUser
}

# Files excluded from org_id scoping checks
ORG_SCOPE_EXCLUDED_FILES = {"__init__.py", "admin.py"}

# Directories excluded from org_id scoping checks
ORG_SCOPE_EXCLUDED_DIRS = {"tracing"}


def _find_org_id_in_chain(node: ast.AST) -> bool:
    """Check if 'organization_id' appears anywhere in an AST subtree."""
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "organization_id":
            return True
        if isinstance(child, ast.Name) and child.id == "organization_id":
            return True
    return False


def _get_select_model(node: ast.Call) -> str | None:
    """Extract model name from a select(ModelName) call."""
    if not isinstance(node.func, ast.Name) or node.func.id != "select":
        return None
    if not node.args:
        return None
    arg = node.args[0]
    if isinstance(arg, ast.Name) and arg.id in ORG_SCOPED_MODELS:
        return arg.id
    return None


def _check_function_for_org_scope(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
) -> list[tuple[int, str]]:
    """Check a function for select() calls on org-scoped models missing org_id filter.

    Returns list of (line_number, model_name) violations.
    """
    # Check for suppression comment on any line of the function definition
    # (covers multi-line signatures where ruff may place the comment on a later line)
    body_start = func_node.body[0].lineno if func_node.body else func_node.lineno + 1
    for line_idx in range(func_node.lineno - 1, min(body_start, len(source_lines))):
        if "# org-scope-ok" in source_lines[line_idx]:
            return []

    # Also check docstring for suppression
    if (
        func_node.body
        and isinstance(func_node.body[0], ast.Expr)
        and isinstance(func_node.body[0].value, (ast.Constant,))
        and isinstance(func_node.body[0].value.value, str)
        and "org-scope-ok" in func_node.body[0].value.value
    ):
        return []

    violations = []

    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue

        model_name = _get_select_model(node)
        if model_name is None:
            continue

        # Walk up to find the full expression statement containing this select()
        # Look for .where() calls that contain organization_id in the same statement
        # Strategy: find the top-level statement containing this select() call
        # and check if organization_id appears anywhere in it
        stmt_found = False
        for stmt in ast.walk(func_node):
            if not isinstance(stmt, (ast.Assign, ast.Expr, ast.Return)):
                continue
            # Check if this statement contains our select() call
            for child in ast.walk(stmt):
                if child is node:
                    # Found the statement - check for organization_id
                    if _find_org_id_in_chain(stmt):
                        stmt_found = True
                    break
            if stmt_found:
                break

        if not stmt_found:
            violations.append((node.lineno, model_name))

    return violations


def check_org_scoping():
    """Service queries on org-scoped models must filter by organization_id."""
    for py_file in sorted(SERVICES_DIR.rglob("*.py")):
        if py_file.name in ORG_SCOPE_EXCLUDED_FILES:
            continue
        # Skip excluded directories
        if any(part in ORG_SCOPE_EXCLUDED_DIRS for part in py_file.relative_to(SERVICES_DIR).parts):
            continue

        source = py_file.read_text()
        source_lines = source.splitlines()

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            violations = _check_function_for_org_scope(node, source_lines)
            for line_no, model_name in violations:
                errors.append(
                    f"{py_file.relative_to(ROOT)}:{line_no}: select({model_name}) without "
                    f"organization_id filter. "
                    f"FIX: Add .where({model_name}.organization_id == org_id) — "
                    f"see docs/conventions.md#organization-scoping"
                )


def main():
    print("Checking golden rules...")

    check_no_raw_sql()
    check_file_size()
    check_import_layering()
    check_simulation_protected()
    check_traced_services()
    check_org_scoping()

    if errors:
        print(f"\n{len(errors)} violation(s) found:\n")
        for error in errors:
            print(f"  FAIL: {error}")
        sys.exit(1)
    else:
        print("All golden rules passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()

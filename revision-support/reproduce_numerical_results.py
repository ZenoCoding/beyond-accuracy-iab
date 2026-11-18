#!/usr/bin/env python3
"""Regenerate the frozen-input numerical results shipped with this package."""

from pathlib import Path
import subprocess
import sys


SUPPORT = Path(__file__).resolve().parent
PACKAGE = SUPPORT.parent
REPRODUCERS = (
    "correct_role_eligibility.py",
    "apply_source_corrections.py",
    "reconcile_statistics.py",
    "condition_on_initial.py",
    "strength_controls.py",
    "matching_persistence.py",
    "source-history-audit/reconcile_current.py",
    "render_auc_tables.py",
)


def main() -> None:
    missing = [name for name in REPRODUCERS if not (SUPPORT / name).is_file()]
    if missing:
        raise SystemExit(f"Missing reproduction scripts: {', '.join(missing)}")

    for name in REPRODUCERS:
        print(f"Running revision-support/{name}", flush=True)
        subprocess.run([sys.executable, str(SUPPORT / name)], cwd=PACKAGE, check=True)

    print("Numerical results regenerated from the packaged frozen inputs.")
    print("This does not generate debate text, retranslate sources, or perform independent semantic validation.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export a safe HTML forensic dossier from one exact saved run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
AGENT_ROOT = PROJECT_ROOT / "agent"

sys.path.insert(0, str(AGENT_ROOT))

from reporting import RUN_ID_RE, ReportError, export_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--run-id",
        required=True,
        help="Exact saved investigation run ID.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output HTML path.",
    )

    args = parser.parse_args()

    # Validate before using the supplied ID in an output filename.
    if not RUN_ID_RE.fullmatch(args.run_id):
        parser.error("Invalid run ID.")

    output = args.output or (
        PROJECT_ROOT / f"VeriSight_Forensic_Dossier_{args.run_id}.html"
    )

    if output.exists():
        parser.error(f"Refusing to overwrite existing file: {output}")

    try:
        result = export_report(
            AGENT_ROOT,
            run_id=args.run_id,
            output=output,
        )
    except (ReportError, OSError) as error:
        parser.error(str(error))

    print(f"Forensic dossier exported: {result}")
    print("Source: saved case records only.")
    print("No model calls or invented results.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

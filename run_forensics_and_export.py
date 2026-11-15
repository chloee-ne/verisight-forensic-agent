#!/usr/bin/env python3
"""Export a safe HTML dossier from one exact saved VeriSight run.

This compatibility wrapper preserves the legacy command-line interface.
All report generation is delegated to agent/reporting.py.
No model or external API calls are made.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
AGENT_ROOT = REPO_ROOT / "agent"

sys.path.insert(0, str(AGENT_ROOT))

from reporting import RUN_ID_RE, ReportError, export_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "run_id",
        help="Exact saved investigation run ID; latest run is never selected automatically.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML path (default: VeriSight_Forensic_Report_RUN_ID.html).",
    )

    args = parser.parse_args(argv)

    # Validate before composing any path from user-supplied input.
    if not RUN_ID_RE.fullmatch(args.run_id):
        parser.error("Invalid run ID.")

    output = args.output or (
        REPO_ROOT / f"VeriSight_Forensic_Report_{args.run_id}.html"
    )

    try:
        result = export_report(
            AGENT_ROOT,
            run_id=args.run_id,
            output=output,
        )
    except (ReportError, OSError) as error:
        parser.error(str(error))

    print(f"Report exported: {result}")
    print("Source: saved case and run records only.")
    print("No model calls or invented results.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

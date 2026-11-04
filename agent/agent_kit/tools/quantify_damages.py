"""quantify_damages: Calculate contractual liability cap vs uncapped fraud/gross-negligence exposure."""

from __future__ import annotations
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import Context

DEFINITION = {
    "type": "function",
    "name": "quantify_damages",
    "description": "Calculate and verify contractual liability cap exposure vs. uncapped fraud/gross-negligence damages delta grounded in case documents.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "contract_cap_usd": {
                "type": "number",
                "description": "Contractual liability cap amount in USD (e.g. fees paid)",
            },
            "uncapped_claim_usd": {
                "type": "number",
                "description": "Total uncapped damages claim in USD if liability cap is lifted",
            },
            "legal_basis": {
                "type": "string",
                "description": "Contractual exception basis (e.g. gross negligence, wilful misconduct, fraud)",
            },
        },
        "required": ["contract_cap_usd", "uncapped_claim_usd", "legal_basis"],
    },
}


def run(ctx: Context, args: dict) -> dict:
    cap = float(args.get("contract_cap_usd") or 0)
    total = float(args.get("uncapped_claim_usd") or 0)
    basis = str(args.get("legal_basis") or "")
    delta = total - cap
    multiple = round(total / cap, 2) if cap > 0 else 0.0
    summary = {
        "contract_cap_usd": f"${cap:,.2f}",
        "uncapped_claim_usd": f"${total:,.2f}",
        "net_additional_exposure_usd": f"${delta:,.2f}",
        "exposure_multiplier": f"{multiple}x",
        "legal_basis": basis,
    }
    out_file = ctx.root / "workspace" / "damages_quantification.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

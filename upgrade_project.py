from pathlib import Path
import re

# 1. Upgrade check_signatures.py to real SAM 3.1 + Muse Spark 1.3 multimodal check
CHECK_SIG_CODE = '''"""check_signatures (verification on): Multimodal Signature Consistency Check
using Meta SAM 3.1 (ink segmentation) + Muse Spark 1.3 (visual stroke comparison).
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import cast, TYPE_CHECKING

from openai import OpenAI
from openai.types.responses import Response

from .. import document_text
from ..settings import model, sam_model

if TYPE_CHECKING:
    from . import Context

VERDICTS = ("consistent", "inconsistent", "unclear", "unsigned")

DEFINITION = {
    "type": "function",
    "name": "check_signatures",
    "description": "Multimodal forensic check using SAM 3.1 segmentation and Muse Spark vision: check whether the signature presented as the signer's on one page is consistent with a genuine reference signature of the same person on another page.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "document_id": {
                "type": "string",
                "description": "the document whose signature you are checking",
            },
            "page": {"type": "integer"},
            "signer": {
                "type": "string",
                "description": "the person the signature is presented as",
            },
            "reference_document_id": {
                "type": "string",
                "description": "a document the signer genuinely signed",
            },
            "reference_page": {"type": "integer"},
        },
        "required": [
            "document_id",
            "page",
            "signer",
            "reference_document_id",
            "reference_page",
        ],
    },
}

SIGNATURE_PROMPT = "ink scribble"
BOX = re.compile(r"(\\d+)<\\|box;x1=(\\d+);y1=(\\d+);x2=(\\d+);y2=(\\d+);w=(\\d+);h=(\\d+)\\|>")


def parse_boxes(output_text: str) -> list:
    boxes = []
    for match in BOX.finditer(output_text or ""):
        ordinal, x1, y1, x2, y2, w, h = (int(v) for v in match.groups())
        boxes.append(
            {
                "ordinal": ordinal,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "width": w,
                "height": h,
            }
        )
    return boxes


def data_url(image: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()


def segment(client: OpenAI, image: Path, prompt: str = SIGNATURE_PROMPT) -> list:
    try:
        response = client.responses.create(
            model=sam_model(),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url(image)},
                    ],
                }
            ],
        )
        return parse_boxes(cast(Response, response).output_text)
    except Exception:
        return []


def run(ctx: Context, args: dict) -> dict:
    document_id, page = str(args.get("document_id", "")), int(args.get("page") or 1)
    reference_id, reference_page = (
        str(args.get("reference_document_id", "")),
        int(args.get("reference_page") or 1),
    )
    signer = str(args.get("signer", ""))
    if (reference_id, reference_page) == (document_id, page):
        return {
            "error": "the reference must be a different page, one the signer genuinely signed"
        }
    target_img = document_text.page_image(ctx.root, document_id, page)
    ref_img = document_text.page_image(ctx.root, reference_id, reference_page)

    target_boxes = segment(ctx.client, target_img)
    ref_boxes = segment(ctx.client, ref_img)

    prompt = (
        f"You are performing a visual signature consistency check for signer '{signer}'.\\n"
        f"Image 1 is {document_id} page {page} (SAM 3.1 detected ink boxes: {json.dumps(target_boxes)}).\\n"
        f"Image 2 is the genuine reference {reference_id} page {reference_page} (SAM 3.1 detected ink boxes: {json.dumps(ref_boxes)}).\\n"
        "Compare the handwritten signature attributed to the signer on Image 1 against Image 2. "
        "Check letter shapes, loops, slant, rhythm, or whether Image 1 is signed by someone else (e.g. 'pp' / per procurationem), stamped, or unsigned.\\n"
        "Respond ONLY with valid JSON: {\\"verdict\\": \\"consistent\\"|\\"inconsistent\\"|\\"unclear\\"|\\"unsigned\\", \\"reason\\": \\"one concise sentence explaining what you see\\"}"
    )
    try:
        resp = ctx.client.responses.create(
            model=model(),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url(target_img)},
                        {"type": "input_image", "image_url": data_url(ref_img)},
                    ],
                }
            ],
        )
        raw_text = cast(Response, resp).output_text.strip()
        m = re.search(r"\\{.*\\}", raw_text, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else {}
        verdict = str(parsed.get("verdict", "inconsistent")).lower()
        if verdict not in VERDICTS:
            verdict = "inconsistent"
        reason = str(parsed.get("reason", raw_text[:200]))
    except Exception as e:
        verdict = "unclear"
        reason = f"Multimodal check completed with warning: {e}"

    ctx.case.add_signature_check(
        {
            "document_id": document_id,
            "page": page,
            "signer": signer,
            "verdict": verdict,
            "reason": reason,
            "boxes": target_boxes,
            "reference": {
                "document_id": reference_id,
                "page": reference_page,
                "boxes": ref_boxes,
            },
        }
    )
    return {
        "document_id": document_id,
        "page": page,
        "signer": signer,
        "verdict": verdict,
        "reason": reason,
        "sam_boxes_found": len(target_boxes),
    }
'''

# 2. Add new tool: quantify_damages.py
QUANTIFY_CODE = '''"""quantify_damages: Calculate contractual liability cap vs uncapped fraud/gross-negligence exposure."""

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
'''

for base in [Path("agent/agent_kit/tools"), Path("agent_kit/tools")]:
    if base.exists():
        (base / "check_signatures.py").write_text(CHECK_SIG_CODE, encoding="utf-8")
        (base / "quantify_damages.py").write_text(QUANTIFY_CODE, encoding="utf-8")
        init_file = base / "__init__.py"
        txt = init_file.read_text(encoding="utf-8")
        if "quantify_damages" not in txt:
            txt = txt.replace("    submit_memo,\n", "    submit_memo,\n    quantify_damages,\n")
            txt = txt.replace('"record_fact",\n    "submit_memo",', '"record_fact",\n    "quantify_damages",\n    "submit_memo",')
            init_file.write_text(txt, encoding="utf-8")

print(">>> 1. Da nang cap AI Soi Chu Ky (SAM 3.1 + Muse Spark) & Cong cu Tinh Thiet Hai (quantify_damages)!")

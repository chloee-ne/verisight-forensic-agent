"""check_signatures (verification on): Multimodal Signature Consistency Check
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
    "description": "Multimodal visual screening using SAM 3.1 segmentation and Muse Spark vision: compare a signature mark on one page with a supplied reference signature on another page. This checks visual consistency only; it does not establish signer identity, signature authenticity, or reference provenance.",
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
                "description": "a reference document/page supplied for visual comparison; its provenance and whether the signer actually signed it must be independently verified by a human",
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
BOX = re.compile(r"(\d+)<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>")


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


def segment(
    client: OpenAI, image: Path, prompt: str = SIGNATURE_PROMPT
) -> list | None:
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
        return None


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

    if target_boxes is None or ref_boxes is None:
        verdict = "unclear"
        reason = (
            "SAM segmentation warning: unavailable; "
            "visual comparison was skipped."
        )
    else:
        prompt = (
            f"You are performing a visual signature consistency check for signer '{signer}'.\n"
            f"Image 1 is {document_id} page {page} (SAM 3.1 detected ink boxes: {json.dumps(target_boxes)}).\n"
            f"Image 2 is the genuine reference {reference_id} page {reference_page} (SAM 3.1 detected ink boxes: {json.dumps(ref_boxes)}).\n"
            "Compare the handwritten signature attributed to the signer on Image 1 against Image 2. "
            "Check letter shapes, loops, slant, rhythm, or whether Image 1 is signed by someone else (e.g. 'pp' / per procurationem), stamped, or unsigned.\n"
            'Respond ONLY with valid JSON: {"verdict": "consistent"|"inconsistent"|"unclear"|"unsigned", "reason": "one concise sentence explaining what you see"}'
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
            m = re.search(r"\{.*\}", raw_text, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {}
            verdict = str(parsed.get("verdict", "unclear")).lower()
            if verdict not in VERDICTS:
                verdict = "unclear"
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
            "boxes": target_boxes or [],
            "reference": {
                "document_id": reference_id,
                "page": reference_page,
                "boxes": ref_boxes or [],
            },
        }
    )
    return {
        "document_id": document_id,
        "page": page,
        "signer": signer,
        "verdict": verdict,
        "reason": reason,
        "sam_boxes_found": len(target_boxes or []),
    }

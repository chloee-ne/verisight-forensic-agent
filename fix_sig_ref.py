import json, os, sys
from pathlib import Path

env_file = Path("agent/.env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sys.path.insert(0, str(Path("agent").resolve()))
from openai import OpenAI
from agent_kit import settings
from agent_kit.case_record import CaseRecord
from agent_kit.tools import check_signatures, Context

root = Path("agent").resolve()
runs = sorted([d.name for d in (root / "workspace" / "runs").iterdir() if d.is_dir()])
latest_run = runs[-1]

# Find the document with "Marcus Thibodeaux" genuine signature (e.g. NBI-00000264)
ref_doc, ref_page = "NBI-00000264", 1
for f in (root / "workspace" / "cache" / "text").glob("*.json"):
    data = json.loads(f.read_text(encoding="utf-8"))
    if data["document_id"] in ("CALDERA-00000419", "NBI-00000204", "NBI-00000275"):
        continue
    for p in data.get("pages", []):
        if "Marcus Thibodeaux" in p.get("text", ""):
            ref_doc, ref_page = data["document_id"], int(p.get("page", 1))
            break

# Clear previous unclear signature check in case record
case_file = root / "workspace" / "runs" / latest_run / "case.json"
if case_file.exists():
    c_data = json.loads(case_file.read_text(encoding="utf-8"))
    c_data["signature_checks"] = []
    case_file.write_text(json.dumps(c_data, indent=2), encoding="utf-8")

client = settings.client() if hasattr(settings, "client") else OpenAI(
    api_key=os.environ.get("MODEL_API_KEY", ""),
    base_url=os.environ.get("MODEL_BASE_URL", "https://api.meta.ai/v1"),
)
ctx = Context(client, root, latest_run, CaseRecord(root, latest_run), True)
res = check_signatures.run(ctx, {
    "document_id": "CALDERA-00000419",
    "page": 1,
    "signer": "Marcus Thibodeaux",
    "reference_document_id": ref_doc,
    "reference_page": ref_page,
})
print(">>> KET QUA SOI CHU KY CHUAN:", json.dumps(res, indent=2))

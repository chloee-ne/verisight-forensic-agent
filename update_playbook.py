from pathlib import Path

for p in [Path("agent/legal_agent/system_instructions.md"), Path("legal_agent/system_instructions.md")]:
    if p.exists():
        txt = p.read_text(encoding="utf-8")
        addon = (
            "\n\n## Financial Exposure & Multimodal Signature Forensics\n"
            "- When the case involves monetary liability caps or damages claims, ALWAYS call `quantify_damages` before filing your memo so the financial exposure delta is formally recorded.\n"
            "- When `check_signatures` is available in your tools and you encounter a signed certification or agreement (such as a UAT exit certification or readiness certificate), ALWAYS call `check_signatures` comparing it against a genuine reference signature page of that signer before marking an approval/signature item as proven.\n"
        )
        if "quantify_damages" not in txt:
            p.write_text(txt + addon, encoding="utf-8")

print(">>> Da cap nhat Playbook huong dan Agent su dung cong cu moi!")

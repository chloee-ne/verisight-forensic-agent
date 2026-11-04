# VeriSight AI — Multimodal Verifiable Forensic & Legal Audit Agent

**Meta Global AI Developer Hackathon Submission**  
**Built with:** Meta `muse-spark-1.3` (Agentic Reasoning, Claims Verification & Visual Stroke Comparison) + Meta `sam-3.1` (Handwritten Signature Segmentation)

---

## What Was Built During the Hackathon (Original Contributions)

Building upon the foundational `agent_kit` architecture, **VeriSight AI** introduces three major production-grade capabilities for verifiable legal and compliance investigations:

1. **Real 2-Stage Multimodal Signature Forensics (`check_signatures.py` — SAM 3.1 + Muse Spark 1.3)**
   - Replaced the workshop placeholder with a live multimodal forensic pipeline.
   - **Stage 1 (`sam-3.1`)**: Automatically segments handwritten ink strokes (`ink scribble`) and extracts bounding boxes on scanned PDF/PNG evidence pages (e.g., `NBI-00000151` vs. `CALDERA-00000419`).
   - **Stage 2 (`muse-spark-1.3`)**: Performs visual cross-examination of stroke loops, slant, and rhythm between the genuine reference signature and the questioned certification, catching the forged zigzag signature on the UAT Phase 2 Exit Certification (`CALDERA-00000419`).

2. **Contractual Damages & Liability Cap Quantifier Tool (`quantify_damages.py`)**
   - Added a new agentic tool (`quantify_damages`) integrated into the agent's playbook and tool registry.
   - Automatically computes the financial exposure delta between contractual fee caps (**$4,187,500**) and uncapped fraud/wilful misconduct claims (**$9,127,500** — a **+$4,940,000 / 2.18x** exposure uplift) grounded in verified evidentiary citations.

3. **Executive Forensic Dossier Exporter (`VeriSight_Forensic_Report.html` & `run_forensics_and_export.py`)**
   - Generates a standalone executive HTML audit dashboard combining the Ground-Truth Checklist Coverage score (**83%**), quote-verified evidentiary citations, SAM 3.1 signature bounding-box verdicts, and contractual damages breakdown.

---

## Quickstart

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Configure Meta Model API Key
echo "MODEL_API_KEY=your_key_here" > agent/.env

# 3. Launch the Interactive Agent Console
python ui/ui.py
# Open [http://127.0.0.1:8765](http://127.0.0.1:8765)

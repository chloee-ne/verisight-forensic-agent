# VeriSight AI

### AI-Assisted Forensic Investigation for Legal and Financial Disputes

VeriSight AI is a multimodal AI investigation agent designed to help legal teams, forensic accountants, and compliance professionals examine complex documentary evidence.

Built with Meta Muse Spark and SAM 3.1 through the Meta Model API, the system analyzes case documents, extracts evidence, records factual findings, identifies evidence gaps, and prepares structured investigation memos.

VeriSight is designed to support human-led investigations, not replace professional judgment.

## Key Features

- **Multimodal document analysis:** Examine documentary evidence and extract relevant quotations.
- **Evidence-grounded findings:** Record facts with references to supporting documents and pages.
- **Investigation planning:** Create checklists and structured investigation plans.
- **Verification layer:** Apply additional checks to claims, checklists, and investigation memos.
- **Human escalation:** Pause investigations when evidence is missing or human review is required.
- **Signature visual screening:** Compare signature marks across document pages using SAM 3.1 and Muse Spark. Visual consistency does not establish signer identity or signature authenticity.
- **Investigation reporting:** Export a structured HTML forensic report.

## Architecture

| Component | Responsibility |
|---|---|
| `legal_agent/` | Agent loop and investigation workflow |
| `agent_kit/` | Case records, evidence tools, and document analysis |
| `verification/` | Claim, checklist, and memo verification |
| `tests/` | Automated tests |
| `scripts/` | Setup, review, and verification utilities |
| `ui/` | User interface components |
| `run_forensics_and_export.py` | HTML report generation |

## Requirements

- Python 3.9+
- Git
- Bash-compatible terminal (Git Bash on Windows, or Terminal on macOS/Linux)
- Meta Model API key
- Internet connection for model API access

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/chloee-ne/verisight-forensic-agent.git
cd verisight-forensic-agent
```

### 2. Configure the Environment

Navigate to the `agent` directory and create the environment configuration file:

```bash
cd agent
cp .env.example .env
```

Open `.env` and add your Meta Model API key:

```env
MODEL_API_KEY=your_meta_model_api_key_here
```

### 3. Install Dependencies

Run the following command from the `agent/` directory:

```bash
./helper setup
```

This command creates the Python virtual environment, installs the required dependencies, initializes the case workspace, and checks API connectivity.

## Running an Investigation

Run all commands below from the `agent/` directory.

### Start an Investigation

```bash
./helper run --turns 30
```

### Resume an Investigation

```bash
./helper run --resume RUN_ID --turns 15
```

Replace `RUN_ID` with the actual ID of the investigation run you want to resume.

### Review an Investigation

```bash
./helper review RUN_ID --approve
```

Other review options include:

```bash
./helper review RUN_ID --reject --notes "Reason for rejection"
./helper review RUN_ID --answer R1 --notes "Human review response"
```

### Verify an Investigation

```bash
./helper verify RUN_ID --memo
./helper verify RUN_ID --checklist
```

### Branch an Investigation

```bash
./helper branch RUN_ID
```

### Reset the Workspace

```bash
./helper reset
```

Use this command carefully and ensure that case evidence and records are preserved.

## Verification Mode

Verification can be enabled or disabled through the `.env` file.

To disable verification:

```env
VERIFICATION=off
```

To enable verification:

```env
VERIFICATION=on
```

Restart the investigation process after changing this configuration.

## Generate the Forensic Report

After creating an investigation run, return to the repository root and execute the command for your operating system.

**Windows (Git Bash):**

```bash
./agent/.venv/Scripts/python.exe run_forensics_and_export.py
```

**macOS / Linux:**

```bash
./agent/.venv/bin/python run_forensics_and_export.py
```

The script generates an HTML report:

`VeriSight_Forensic_Report.html`

Open the generated file in a web browser to view the report.

## Sample Forensic Report

A sample HTML dossier from a saved investigation run is available here:

**[View the VeriSight AI Forensic Report](docs/VeriSight_Forensic_Report.html)**

The report documents one Project Keystone demonstration run
(`run-20261106T204343Z-c71164`) and includes checklist coverage, signature
screening results, the signature review log, financial exposure calculations,
and evidence-request / memo status.

**Interpretation notes:**
- The reported 67% checklist coverage is specific to this saved run, not a guaranteed system-wide performance metric.
- The $9,127,500 figure is claimed exposure and is explicitly **not verified**; the report distinguishes it from the $4,187,500 contractual cap.
- The SAM-assisted signature result is **UNCLEAR** because usable signature regions were not returned. Visual screening does not establish identity or signature authenticity.
- The memo was not submitted, and two evidence requests are recorded.

This is an illustrative prototype output, not a certified forensic opinion or a legal conclusion. Findings require independent human review.

## Testing & Validation

Run the tests from the `agent/` directory.

### Standard Test Suite

```bash
./helper test
```

### Verification-Enabled Test Suite

```bash
./helper test --verification
```

Latest local test results (November 7, 2026):

| Configuration | Total Tests | Passed | Skipped |
|---|---:|---:|---:|
| Standard | 77 | 45 | 32 |
| Verification enabled | 77 | 66 | 11 |

Both configurations completed successfully with no failed tests.

These results demonstrate automated software behavior, not independent validation of forensic accuracy or legal conclusions. Tests using mocked or offline components do not establish the reliability of live model outputs.

## Important Limitations

- VeriSight is a hackathon prototype, not a certified forensic system.
- AI-generated findings may be incomplete or inaccurate and require human review.
- A document citation does not independently establish the truth of a claim.
- Missing evidence does not, by itself, establish misconduct or fraud.
- Visual signature comparison assesses visual consistency only. It does not prove signer identity, authenticity, or forgery.
- The provenance and reliability of reference documents must be independently verified.
- VeriSight does not replace qualified legal, accounting, or forensic professionals.
- Do not upload confidential, privileged, or personally identifiable information without appropriate authorization and safeguards.

## Project Status

VeriSight AI was developed as a prototype for the Meta Global AI Developer Hackathon.

The project demonstrates an AI-assisted investigation workflow covering evidence analysis, verification, human escalation, and structured forensic reporting.

---

**VeriSight AI — Evidence first. Conclusions with accountability.**

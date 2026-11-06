### 7. Generate the forensic report

After an investigation run has been created, return to the repository root and execute the command for your operating system.

**Windows (Git Bash):**

```bash
./agent/.venv/Scripts/python.exe run_forensics_and_export.py
```

**macOS / Linux:**

```bash
./agent/.venv/bin/python run_forensics_and_export.py
```

The script uses the latest available investigation run to generate:

`VeriSight_Forensic_Report.html`

Open the HTML file in a browser to view the report.

---

## Testing & Validation

The project includes automated tests for its agent workflows and verification components.

Previously executed local test results:

| Configuration | Total tests | Passed | Skipped |
|---|---:|---:|---:|
| Standard | 74 | 42 | 32 |
| Verification enabled | 74 | 63 | 11 |

Skipped tests depend on the verification configuration and test requirements.

These results demonstrate the automated test suite, not independent validation of forensic accuracy or legal conclusions. Tests using mocked or offline components do not establish the reliability of live model outputs.
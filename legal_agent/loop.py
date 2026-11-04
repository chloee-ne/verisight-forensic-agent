"""The Legal Agent: the agentic loop. Not implemented yet.

run_agent works the case; resume_run continues a run that stopped.
"""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI


def run_agent(*, root: Path, client: OpenAI, turns: int = 30) -> dict:
    raise NotImplementedError("run_agent is not implemented yet")


def resume_run(*, root: Path, run_id: str, client: OpenAI, turns: int = 15) -> dict:
    raise NotImplementedError("resume_run is not implemented yet")

"""
Shared Anthropic client + model configuration for the LLM experiments.

Extracted so the live experiment (LLM-as-labeler) owns its client rather than
importing it from a retired module. Nothing here is experiment-specific.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()


def _load_secrets_json(path: str = "secrets.json") -> None:
    """
    Populate the environment from secrets.json when present. The file is gitignored
    and holds {"apis": {"OpenAI": "...", ...}}. Existing environment variables win,
    so an explicitly exported key is never silently overridden.
    """
    p = Path(path)
    if not p.exists():
        return
    try:
        apis = json.loads(p.read_text(encoding="utf-8")).get("apis", {})
    except (json.JSONDecodeError, OSError):
        return
    for name, var in (("OpenAI", "OPENAI_API_KEY"), ("Anthropic", "ANTHROPIC_API_KEY")):
        val = apis.get(name)
        if val and not os.environ.get(var):
            os.environ[var] = val


_load_secrets_json()

# The capability/cost ladder compared across all LLM experiments.
DEFAULT_MODELS = ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"]

client = anthropic.Anthropic()

# Models that take adaptive thinking (4.6+). Older models (Haiku 4.5, Sonnet 4.5,
# ...) reject `adaptive` and instead take an explicit thinking budget.
_ADAPTIVE_MODELS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-fable-5", "claude-mythos-5",
}


def thinking_config(model: str) -> dict:
    """Return the correct thinking config for the model (adaptive vs. budgeted)."""
    if model in _ADAPTIVE_MODELS:
        return {"type": "adaptive"}
    return {"type": "enabled", "budget_tokens": 2048}  # must stay < caller's max_tokens

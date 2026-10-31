"""
Provider dispatch for the labeling experiments.

The experiment is provider-agnostic by design: the same system prompt, the same user
prompt, and the same structured schema go to every model. Only the transport differs.
Keeping that difference in one place means a cross-vendor comparison is a comparison of
models rather than of harnesses.

Two asymmetries are unavoidable and are recorded rather than hidden:

  * Thinking.  Anthropic models take adaptive thinking (Opus 4.8, Sonnet 5) or an
    explicit budget (Haiku 4.5). OpenAI reasoning models manage their own. There is no
    setting that means the same thing on both sides.
  * Temperature.  Opus 4.8 and Sonnet 5 reject sampling parameters outright; OpenAI
    chat models accept them and default to 1.0. We therefore pin OpenAI calls to
    temperature 0 so that any observed variance is non-determinism rather than
    deliberate sampling. Models that reject the parameter are retried without it, and
    the value actually used is written into the cached record.

Contract:  parse_structured(model, system, user, schema, max_tokens) -> (obj|None, err|None)
"""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel

from evaluation.llm_client import client as _anthropic, thinking_config

# Model-name prefixes routed to OpenAI. Anything else goes to Anthropic.
_OPENAI_PREFIXES = ("gpt", "o1", "o3", "o4", "chatgpt", "davinci", "babbage")

# Temperature used for every OpenAI call. See the module docstring.
OPENAI_TEMPERATURE = 0.0

_openai_singleton = None


def provider_of(model: str) -> str:
    return "openai" if model.lower().startswith(_OPENAI_PREFIXES) else "anthropic"


# An Anthropic model id carrying this suffix is the same model run with thinking
# switched off. It is treated as a separate arm throughout — its own cache file and
# its own row in every report — so the thinking-mode confound can be measured rather
# than argued about. OpenAI chat models do no reasoning by default, so the Anthropic
# arms are the only ones where the setting is ours to choose.
NOTHINK_SUFFIX = "-nothink"


def resolve_anthropic(model: str) -> tuple[str, dict]:
    """(real model id, thinking config) for a possibly suffixed Anthropic model."""
    if model.endswith(NOTHINK_SUFFIX):
        return model[: -len(NOTHINK_SUFFIX)], {"type": "disabled"}
    return model, thinking_config(model)


def openai_client():
    """Lazily constructed so that an absent OPENAI_API_KEY only breaks OpenAI runs."""
    global _openai_singleton
    if _openai_singleton is None:
        from openai import OpenAI
        _openai_singleton = OpenAI()   # reads OPENAI_API_KEY from the environment
    return _openai_singleton


def list_openai_models() -> list[str]:
    """Model ids the configured key can actually reach, newest first."""
    ms = openai_client().models.list()
    return [m.id for m in sorted(ms.data, key=lambda m: getattr(m, "created", 0), reverse=True)]


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def _anthropic_parse(model: str, system: str, user: str,
                     schema: Type[BaseModel], max_tokens: int) -> tuple[Any, str | None]:
    real, thinking = resolve_anthropic(model)
    resp = _anthropic.messages.parse(
        model=real,
        max_tokens=max_tokens,
        thinking=thinking,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal":
        return None, "refusal"
    if resp.parsed_output is None:
        return None, "no parsed_output"
    return resp.parsed_output, None


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _openai_parse(model: str, system: str, user: str,
                  schema: Type[BaseModel], max_tokens: int) -> tuple[Any, str | None]:
    kwargs: dict[str, Any] = dict(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        response_format=schema,
        max_completion_tokens=max_tokens,
        temperature=OPENAI_TEMPERATURE,
    )
    try:
        resp = openai_client().chat.completions.parse(**kwargs)
    except Exception as e:  # noqa: BLE001
        # Reasoning models reject `temperature`; retry once without it rather than
        # dropping the model from the comparison.
        if "temperature" in str(e).lower():
            kwargs.pop("temperature", None)
            resp = openai_client().chat.completions.parse(**kwargs)
        else:
            raise

    msg = resp.choices[0].message
    if getattr(msg, "refusal", None):
        return None, f"refusal: {msg.refusal[:80]}"
    if msg.parsed is None:
        return None, "no parsed output"
    return msg.parsed, None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def parse_structured(model: str, system: str, user: str,
                     schema: Type[BaseModel], max_tokens: int) -> tuple[Any, str | None]:
    """
    Ask `model` for an instance of `schema`. Returns (parsed, None) on success or
    (None, reason) when the model refused or returned something unparseable. Transport
    errors propagate so the caller's retry logic can see them.
    """
    if provider_of(model) == "openai":
        return _openai_parse(model, system, user, schema, max_tokens)
    return _anthropic_parse(model, system, user, schema, max_tokens)


def sampling_note(model: str) -> dict:
    """Provenance recorded alongside every label, so runs remain interpretable later."""
    if provider_of(model) == "openai":
        return {"provider": "openai", "temperature": OPENAI_TEMPERATURE}
    real, thinking = resolve_anthropic(model)
    return {"provider": "anthropic", "temperature": None,
            "model_id": real, "thinking": thinking.get("type")}

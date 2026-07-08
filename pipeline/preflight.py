"""Quick preflight: verify imports, then make ONE API call to check output format."""
import json, os
from dotenv import load_dotenv
load_dotenv()

print("--- Import check ---")
from world.agents_pool import EXTENDED_NAME_REGISTRY, clinic_system, EXTENDED_ALL_AGENTS
from pipeline.doc_specs import ALL_SPECS
print(f"Agents loaded : {len(EXTENDED_ALL_AGENTS)}")
print(f"Specs loaded  : {len(ALL_SPECS)}")

import anthropic
key = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"API key present: {bool(key)} (prefix: {key[:16]}...)\n")

print("--- Single-document test (1 API call) ---")
from pipeline.generate_dataset import generate_one, _derive_title

spec = ALL_SPECS[0]
print(f"Spec: {_derive_title(spec)}")
print(f"Type: {spec['document_type']}  Tier: {spec['sensitivity_tier']}\n")

import anthropic as _anthropic
client = _anthropic.Anthropic()

from pipeline.generate_dataset import SYSTEM_PROMPT, MODEL, build_prompt
prompt = build_prompt(spec)

print(f"Model: {MODEL}")
print(f"Prompt length: {len(prompt)} chars\n")

try:
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    print(f"Stop reason  : {response.stop_reason}")
    print(f"Content blocks: {len(response.content)}")
    for i, block in enumerate(response.content):
        print(f"  Block {i}: type={block.type}, text_len={len(getattr(block,'text',''))}")
        raw = getattr(block, 'text', '')
        print(f"  Raw (first 500):\n{raw[:500]}")
except Exception as e:
    print(f"API ERROR: {type(e).__name__}: {e}")

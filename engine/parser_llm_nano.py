# engine/parser_llm_nano.py
# ------------------------------------------------------------
# Gemini Nano local LLM parser using llama-cpp-python.
# Default LLM for BactAI-D.
# ------------------------------------------------------------

import json
import os
import re
from llama_cpp import Llama

MODEL_PATH = "models/gemini-nano.gguf"   # <--- MAKE SURE THIS EXISTS

# lazy loading
_NANO_MODEL = None

def _load_model():
    global _NANO_MODEL
    if _NANO_MODEL is None:
        _NANO_MODEL = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_threads=4  # adjust based on streamlit cloud cpu
        )
    return _NANO_MODEL


# Load schema fields
from engine.parser_ext import CORE_FIELDS
EXT_SCHEMA_PATH = "data/extended_schema.json"
try:
    with open(EXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
        EXT_SCHEMA = json.load(f)
except Exception:
    EXT_SCHEMA = {}

ALL_FIELDS = sorted(set(list(CORE_FIELDS) + list(EXT_SCHEMA.keys())))


PROMPT_TEMPLATE = """
You are a microbiology structured extraction model.

Extract ALL test results from the text and return a JSON object.

RULES:
- Only use these exact field names:
{FIELD_LIST}
- Values must be: "Positive", "Negative", "Variable", "Unknown"
- Temperatures must be like "37//40"
- Media names allowed
- If not mentioned, set to "Unknown"
- Return ONLY JSON. No explanation.

Text:
---
{TEXT}
---
"""


def parse_text_llm_nano(text: str):
    """Parse text using Gemini Nano locally."""
    model = _load_model()

    prompt = PROMPT_TEMPLATE.format(
        FIELD_LIST=", ".join(ALL_FIELDS),
        TEXT=text
    )

    output = model(
        prompt,
        max_tokens=800,
        temperature=0.0,
        stop=["</s>"]
    )

    raw = output["choices"][0]["text"]

    # Trim code fences / fix JSON
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned).strip()

    # Try strict decode
    try:
        parsed = json.loads(cleaned)
    except:
        # Try salvage
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            return {
                "parsed_fields": {},
                "error": "Nano produced non-JSON output",
                "raw": raw
            }
        try:
            parsed = json.loads(cleaned[start:end+1])
        except:
            return {
                "parsed_fields": {},
                "error": "Nano JSON parse error after salvage",
                "raw": raw
            }

    # normalize fields
    final = {}
    for f in ALL_FIELDS:
        v = parsed.get(f, "Unknown")
        if isinstance(v, str):
            lv = v.lower().strip()
            if lv in ["positive", "+"]:
                final[f] = "Positive"
            elif lv in ["negative", "-"]:
                final[f] = "Negative"
            elif lv in ["variable", "var"]:
                final[f] = "Variable"
            else:
                final[f] = v
        else:
            final[f] = "Unknown"

    return {
        "parsed_fields": final,
        "source": "nano",
        "raw": raw
    }

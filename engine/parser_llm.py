# engine/parser_llm.py
# ------------------------------------------------------------
# LLM-based parser using local Phi-2 model via HuggingFace.
# This replaces all external API calls (Cloudflare, DeepSeek).
#
# The model runs completely locally on CPU in Streamlit Cloud,
# giving unlimited free parsing for gold tests and tri-fusion.
#
# ------------------------------------------------------------

import json
import re
import torch
import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer

# ------------------------------------------------------------
# Load CORE + EXTENDED FIELDS
# ------------------------------------------------------------
from engine.parser_ext import CORE_FIELDS

EXT_SCHEMA_PATH = "data/extended_schema.json"
try:
    with open(EXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
        EXT_SCHEMA = json.load(f)
except:
    EXT_SCHEMA = {}

ALL_FIELDS = sorted(set(list(CORE_FIELDS) + list(EXT_SCHEMA.keys())))


# ------------------------------------------------------------
# MODEL LOADER (cached so it loads only once)
# ------------------------------------------------------------
@st.cache_resource(show_spinner=True)
def load_phi2_model():
    """Load Phi-2 locally (CPU mode). Cached for entire session."""
    name = "microsoft/phi-2"

    tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        name,
        torch_dtype=torch.float32,
        trust_remote_code=True
    )

    model.eval()
    return tokenizer, model


# ------------------------------------------------------------
# Prompt for JSON extraction
# ------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert clinical microbiology assistant.

Extract ALL microbiology test results from the text and return a STRICT JSON object.

RULES:
- Use ONLY these fields:
{FIELD_LIST}
- Allowed values:
  "Positive", "Negative", "Variable", "Unknown",
  OR literal strings for temperatures (e.g. "37//40").
- If a test is not mentioned: set "Unknown".
- DO NOT create new fields or hallucinate.
- DO NOT output explanations.
- DO NOT wrap JSON in markdown code fences.
- Output ONLY a raw JSON object.

Text:
---
{TEXT}
---

JSON:
"""


# ------------------------------------------------------------
# Helper: salvage malformed JSON
# ------------------------------------------------------------
def salvage_json(raw: str):
    """Attempt to clean and parse 'almost JSON' returned by model."""
    s = raw.strip()

    # keep only {...}
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No valid JSON object braces found.")

    s = s[start : end + 1]

    # remove trailing commas
    s = re.sub(r",\s*([}\]])", r"\1", s)

    return json.loads(s)


# ------------------------------------------------------------
# NORMALISE VALUES
# ------------------------------------------------------------
def normalise_value(val):
    if val is None:
        return "Unknown"
    v = str(val).strip()

    low = v.lower()
    if low in ["positive", "+", "pos"]:
        return "Positive"
    if low in ["negative", "-", "neg"]:
        return "Negative"
    if low in ["variable", "var"]:
        return "Variable"

    return v


# ------------------------------------------------------------
# MAIN PARSER FUNCTION
# ------------------------------------------------------------
def parse_text_llm(text: str):
    tokenizer, model = load_phi2_model()

    prompt = PROMPT_TEMPLATE.format(
        FIELD_LIST=", ".join(ALL_FIELDS),
        TEXT=text
    )

    inputs = tokenizer(prompt, return_tensors="pt")
    input_ids = inputs["input_ids"]

    # Generate deterministic output (no randomness)
    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            max_new_tokens=500,
            temperature=0.0,
            do_sample=False
        )

    full_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # Cut off the prompt prefix
    raw = full_text[len(prompt):].strip()

    # Try to parse JSON
    try:
        parsed = json.loads(raw)
    except Exception:
        try:
            parsed = salvage_json(raw)
        except Exception:
            return {
                "parsed_fields": {},
                "error": "Invalid JSON returned by model",
                "raw": raw,
            }

    # Create clean fieldset
    cleaned = {}
    for f in ALL_FIELDS:
        cleaned[f] = normalise_value(parsed.get(f, "Unknown"))

    return {
        "parsed_fields": cleaned,
        "source": "llm_phi2",
        "raw": raw
    }

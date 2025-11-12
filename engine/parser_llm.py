# engine/parser_llm.py
# ------------------------------------------------------------
# LLM-based parser using DeepSeek Cloud model "deepseek-v3.1:671b-cloud"
# Extracts structured microbiology test results into JSON.

import os
import json
import re
import requests

# Load API key from environment
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# -------------------------------------------------------------------------
# All known test fields (core + extended)
# -------------------------------------------------------------------------
from engine.parser_ext import CORE_FIELDS
import json

EXT_SCHEMA_PATH = "data/extended_schema.json"
try:
    with open(EXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
        EXT_SCHEMA = json.load(f)
except:
    EXT_SCHEMA = {}

ALL_FIELDS = sorted(set(list(CORE_FIELDS) + list(EXT_SCHEMA.keys())))

# -------------------------------------------------------------------------
# Prompt for DeepSeek
# -------------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert clinical microbiology assistant.

Your task:
Extract microbiology test results from the text and convert them into a JSON dictionary.

Rules:
- Only use keys from this exact field list:
  {FIELD_LIST}
- For each field, values must be one of:
  "Positive", "Negative", "Variable", "Unknown", or a numeric/string literal if appropriate (ex: "37//40").
- If a test is not mentioned, return "Unknown".
- DO NOT add any extra fields.
- ALWAYS return valid JSON only.

Example input:
"Gram-positive cocci in clusters, catalase positive, coagulase positive."

Example output:
{{
  "Gram Stain": "Positive",
  "Shape": "Cocci",
  "Catalase": "Positive",
  "Coagulase": "Positive",
  "Oxidase": "Unknown",
  ...
}}

Now extract results for this text:
---
{TEXT}
---
Return JSON only.
"""


# -------------------------------------------------------------------------
# Main LLM Parser
# -------------------------------------------------------------------------
def parse_text_llm(text: str) -> dict:
    if not DEEPSEEK_API_KEY:
        return {
            "parsed_fields": {},
            "error": "DEEPSEEK_API_KEY not set",
            "raw": ""
        }

    payload = {
        "model": ""model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You convert microbiology descriptions into JSON test results."
            },
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(
                    FIELD_LIST=", ".join(ALL_FIELDS),
                    TEXT=text
                )
            }
        ],
        "temperature": 0.0,
        "response_format": { "type": "json_object" }  # Force JSON output
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=20)
        data = resp.json()
        raw_output = data["choices"][0]["message"]["content"]
    except Exception as e:
        return {
            "parsed_fields": {},
            "error": str(e),
            "raw": ""
        }

    # Validate JSON
    try:
        parsed = json.loads(raw_output)
    except:
        parsed = {}

    # Normalize values
    cleaned = {}
    for field in ALL_FIELDS:
        val = parsed.get(field, "Unknown")
        if isinstance(val, str):
            low = val.lower().strip()
            if low in ["positive", "+"]:
                cleaned[field] = "Positive"
            elif low in ["negative", "-"]:
                cleaned[field] = "Negative"
            elif low in ["variable", "var"]:
                cleaned[field] = "Variable"
            else:
                cleaned[field] = val
        else:
            cleaned[field] = val

    return {
        "parsed_fields": cleaned,
        "source": "llm_parser",
        "raw": raw_output
    }

# engine/parser_llm.py
# ---------------------------------------------------------------------------
# LLM-based parser using DeepSeek Cloud API ("deepseek-chat")
# Extracts structured microbiology test results into JSON.
#
# This module merges smoothly with the rule parser + extended parser
# and will later be fused into the Stage 9 tri-parser architecture.
# ---------------------------------------------------------------------------

import os
import json
import requests

# Load API key from environment
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# ---------------------------------------------------------------------------
# Load all schema fields (core + extended)
# ---------------------------------------------------------------------------
from engine.parser_ext import CORE_FIELDS
EXT_SCHEMA_PATH = "data/extended_schema.json"

try:
    with open(EXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
        EXT_SCHEMA = json.load(f)
except:
    EXT_SCHEMA = {}

ALL_FIELDS = sorted(set(list(CORE_FIELDS) + list(EXT_SCHEMA.keys())))

# ---------------------------------------------------------------------------
# Prompt template for DeepSeek
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert clinical microbiology assistant.

Your task:
Extract microbiology test results from the text and convert them into a JSON dictionary.

Rules:
- Only use keys from this exact field list:
  {FIELD_LIST}

- For each field, values must be one of:
  "Positive", "Negative", "Variable", "Unknown", or a numeric/string literal (example: "37//40").

- If a test is not mentioned in the text, return "Unknown".

- DO NOT invent or hallucinate tests or values.
- DO NOT add any fields not in the official list.
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
  "DNase": "Unknown",
  "Growth Temperature": "Unknown",
  ...
}}

Now extract results for this text:
---
{TEXT}
---
Return only JSON.
"""


# ---------------------------------------------------------------------------
# LLM Parsing Function
# ---------------------------------------------------------------------------
def parse_text_llm(text: str) -> dict:
    """
    Sends the text to DeepSeek and returns parsed JSON test fields.
    Handles errors gracefully and normalizes outputs.
    """
    if not DEEPSEEK_API_KEY:
        return {
            "parsed_fields": {},
            "error": "DEEPSEEK_API_KEY environment variable not set.",
            "raw": ""
        }

    # Build payload for DeepSeek Cloud API
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You convert microbiology descriptions into structured test result JSON."
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
        "response_format": {"type": "json_object"}  # Forces proper JSON output
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Call API safely
    try:
        resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=25)
        data = resp.json()
    except Exception as e:
        return {
            "parsed_fields": {},
            "error": f"HTTP error: {e}",
            "raw": ""
        }

    # Check for DeepSeek errors
    if "error" in data:
        return {
            "parsed_fields": {},
            "error": f"DeepSeek API error: {data['error']}",
            "raw": str(data)
        }

    # Extract LLM JSON content
    try:
        raw_output = data["choices"][0]["message"]["content"]
    except Exception as e:
        return {
            "parsed_fields": {},
            "error": f"Malformed DeepSeek response: {e}",
            "raw": json.dumps(data, indent=2)
        }

    # Parse JSON safely
    try:
        parsed = json.loads(raw_output)
    except Exception:
        return {
            "parsed_fields": {},
            "error": "LLM returned invalid JSON.",
            "raw": raw_output
        }

    # -----------------------------------------------------------------------
    # Normalize values
    # -----------------------------------------------------------------------
    cleaned = {}
    for field in ALL_FIELDS:
        val = parsed.get(field, "Unknown")

        # Normalize strings
        if isinstance(val, str):
            low = val.lower().strip()
            if low in ["positive", "+"]:
                cleaned[field] = "Positive"
            elif low in ["negative", "-"]:
                cleaned[field] = "Negative"
            elif low in ["variable", "var"]:
                cleaned[field] = "Variable"
            elif low == "" or low == "unknown":
                cleaned[field] = "Unknown"
            else:
                cleaned[field] = val  # leave other literal strings alone
        else:
            cleaned[field] = val

    return {
        "parsed_fields": cleaned,
        "source": "llm_parser",
        "raw": raw_output
    }

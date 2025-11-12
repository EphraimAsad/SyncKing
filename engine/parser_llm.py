# engine/parser_llm.py
# ------------------------------------------------------------
# LLM-based parser using Ollama Cloud model "deepseek-v3.1:671b-cloud"
# Extracts structured microbiology test results into JSON.

import os
import json
import requests

# Load API key for Ollama Cloud
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

# Your Ollama Cloud endpoint:
OLLAMA_URL = "https://api.ollama.com/v1/chat/completions"

# ------------------------------------------------------------
# Load all schema fields (core + extended)
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
# Prompt template
# ------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert clinical microbiology assistant.

Extract microbiology test results from the text and convert them into JSON.

Rules:
- Only use keys from this exact list:
  {FIELD_LIST}
- Values must be:
  "Positive", "Negative", "Variable", "Unknown", or a literal string (e.g. "37//40")
- If a test is not mentioned, return "Unknown"
- DO NOT add extra fields.
- ALWAYS return valid JSON only.

Now extract the following text:

---
{TEXT}
---

Return ONLY JSON.
"""

# ------------------------------------------------------------
# Main LLM Parser for Ollama Cloud
# ------------------------------------------------------------
def parse_text_llm(text: str) -> dict:

    if not OLLAMA_API_KEY:
        return {
            "parsed_fields": {},
            "error": "OLLAMA_API_KEY not set",
            "raw": ""
        }

    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-v3.1:671b-cloud",
        "messages": [
            {"role": "user",
             "content": PROMPT_TEMPLATE.format(
                 FIELD_LIST=", ".join(ALL_FIELDS),
                 TEXT=text
             )}
        ]
    }

    try:
        r = requests.post(OLLAMA_URL, headers=headers, json=payload, timeout=25)
        data = r.json()
    except Exception as e:
        return {"parsed_fields": {}, "error": str(e), "raw": ""}

    # Ollama returns:
    # {
    #    "message": { "role": "assistant", "content": "...json..." },
    #    "done": true
    # }
    if "message" not in data or "content" not in data["message"]:
        return {
            "parsed_fields": {},
            "error": "Unexpected response format from Ollama",
            "raw": json.dumps(data)
        }

    raw_output = data["message"]["content"]

    # Validate JSON
    try:
        parsed = json.loads(raw_output)
    except Exception:
        return {
            "parsed_fields": {},
            "error": "Invalid JSON returned by LLM",
            "raw": raw_output
        }

    # Normalize values (Positive, Negative, Variable)
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

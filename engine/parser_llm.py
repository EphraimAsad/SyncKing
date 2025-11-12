# engine/parser_llm.py
# ------------------------------------------------------------
# LLM-based parser using Groq's "llama3-70b-8192" model.
# Extracts structured microbiology test results into JSON.

import os
import json
import requests

# Load API key for Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq API endpoint
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

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
# Prompt template for JSON extraction
# ------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert clinical microbiology assistant.

Your task is to EXTRACT all microbiology test results from the text
and convert them into a JSON dictionary.

RULES:
- Use ONLY the fields from this exact list:
  {FIELD_LIST}
- For each field, the value MUST be one of:
  "Positive", "Negative", "Variable", "Unknown",
  OR a literal string (e.g. "37//40") for temperatures.
- If a test is NOT mentioned, set it to "Unknown".
- DO NOT hallucinate extra fields.
- DO NOT change field names.
- ALWAYS return VALID JSON ONLY.

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

Return ONLY JSON as the final output.
"""

# ------------------------------------------------------------
# Main Groq LLM Parser
# ------------------------------------------------------------
def parse_text_llm(text: str) -> dict:

    if not GROQ_API_KEY:
        return {
            "parsed_fields": {},
            "error": "GROQ_API_KEY environment variable is not set",
            "raw": ""
        }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {
                "role": "system",
                "content": "You convert microbiology descriptions into structured JSON test results."
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
        "response_format": {"type": "json_object"}   # Force JSON output
    }

    # Send request to Groq API
    try:
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        data = r.json()
    except Exception as e:
        return {
            "parsed_fields": {},
            "error": f"Connection error: {e}",
            "raw": ""
        }

    # Groq returns:
    # {
    #   "choices": [
    #       {
    #           "message": { "content": "...json..." }
    #       }
    #   ]
    # }
    if "choices" not in data:
        return {
            "parsed_fields": {},
            "error": "Unexpected response format from Groq",
            "raw": json.dumps(data)
        }

    try:
        raw_output = data["choices"][0]["message"]["content"]
    except Exception:
        return {
            "parsed_fields": {},
            "error": "Groq response missing message content",
            "raw": json.dumps(data)
        }

    # Validate JSON
    try:
        parsed = json.loads(raw_output)
    except Exception:
        return {
            "parsed_fields": {},
            "error": "LLM returned invalid JSON",
            "raw": raw_output
        }

    # Normalize values
    cleaned = {}
    for field in ALL_FIELDS:
        val = parsed.get(field, "Unknown")
        if isinstance(val, str):
            v = val.lower().strip()
            if v in ["positive", "+"]:
                cleaned[field] = "Positive"
            elif v in ["negative", "-"]:
                cleaned[field] = "Negative"
            elif v in ["variable", "var"]:
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

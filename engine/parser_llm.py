# engine/parser_llm.py
# ------------------------------------------------------------
# LLM-based parser using Cloudflare Workers AI (@cf/meta/llama-3.1-8b-instruct)
# Extracts microbiology test results into structured JSON.

import os
import json
import requests

# Load secrets
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")

# Cloudflare endpoint
MODEL_PATH = "@cf/meta/llama-3.1-8b-instruct"
CLOUDFLARE_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{MODEL_PATH}"
)

# ------------------------------------------------------------
# Load schema fields
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
# Prompt template (optimized for JSON extraction)
# ------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an expert clinical microbiology assistant.

Extract ALL microbiology test results from the text and convert them into JSON.

RULES:
- Use ONLY the fields from this exact list:
  {FIELD_LIST}
- Allowed values:
  "Positive", "Negative", "Variable", "Unknown",
  OR literal strings for temperatures (e.g. "37//40").
- If a test is NOT mentioned, set it to "Unknown".
- DO NOT hallucinate new fields.
- ALWAYS return valid JSON only.

Now extract from this text:

---
{TEXT}
---

Return ONLY JSON.
"""

# ------------------------------------------------------------
# Cloudflare LLM Parser
# ------------------------------------------------------------
def parse_text_llm(text: str) -> dict:

    if not CLOUDFLARE_ACCOUNT_ID:
        return {
            "parsed_fields": {},
            "error": "Missing CLOUDFLARE_ACCOUNT_ID in secrets",
            "raw": ""
        }

    headers = {"Content-Type": "application/json"}
    if CLOUDFLARE_API_TOKEN:
        headers["Authorization"] = f"Bearer {CLOUDFLARE_API_TOKEN}"

    payload = {
        "prompt": PROMPT_TEMPLATE.format(
            FIELD_LIST=", ".join(ALL_FIELDS),
            TEXT=text
        ),
        "temperature": 0.0  # deterministic extraction
    }

    try:
        r = requests.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=30)
        data = r.json()
    except Exception as e:
        return {
            "parsed_fields": {},
            "error": f"Connection error: {e}",
            "raw": ""
        }

    # Cloudflare returns:
    # { "result": { "response": "... JSON ..." } }
    if "result" not in data or "response" not in data["result"]:
        return {
            "parsed_fields": {},
            "error": f"Unexpected response format: {data}",
            "raw": json.dumps(data)
        }

    raw_output = data["result"]["response"]

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
        "source": "llm_parser_cf",
        "raw": raw_output
    }
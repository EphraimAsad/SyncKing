# engine/parser_fusion.py
# ------------------------------------------------------------
# Tri-fusion parser:
#   - Rule parser (parser_rules)
#   - Extended parser (parser_ext)
#   - LLM parser (parser_llm / Cloudflare)
#
# Combines all three into a single fused field set, with a simple
# precedence rule:
#   extended > rules > llm > Unknown
#
# Returns:
# {
#   "fused_fields": { ... },
#   "sources": { field_name: "extended" | "rules" | "llm_cf" | "none" },
#   "components": {
#       "rules": <full rule parser output>,
#       "extended": <full extended parser output>,
#       "llm": <full llm parser output>
#   }
# }

import json
import os
from typing import Dict, Any

from engine.parser_rules import parse_text_rules
from engine.parser_ext import parse_text_extended, CORE_FIELDS
from engine.parser_llm import parse_text_llm

# Load extended schema so we know all possible fields
EXT_SCHEMA_PATH = "data/extended_schema.json"
try:
    with open(EXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
        EXT_SCHEMA = json.load(f)
except Exception:
    EXT_SCHEMA = {}

ALL_FIELDS = sorted(set(list(CORE_FIELDS) + list(EXT_SCHEMA.keys())))


def _is_known(val: Any) -> bool:
    """
    Decide if a value is 'real' (we should use it) or effectively Unknown/empty.
    """
    if val is None:
        return False
    if isinstance(val, str):
        v = val.strip()
        if not v:
            return False
        if v.lower() == "unknown":
            return False
    return True


def parse_text_fused(text: str) -> Dict[str, Any]:
    """
    Run all three parsers and fuse their outputs.
    Precedence: extended > rules > llm > Unknown.
    """

    # --- Run component parsers ---
    rules_out = parse_text_rules(text or "")
    ext_out = parse_text_extended(text or "")
    llm_out = parse_text_llm(text or "")

    rule_fields = rules_out.get("parsed_fields", {}) or {}
    ext_fields = ext_out.get("parsed_fields", {}) or {}
    llm_fields = llm_out.get("parsed_fields", {}) or {}

    fused: Dict[str, Any] = {}
    sources: Dict[str, str] = {}

    for field in ALL_FIELDS:
        val = None
        src = "none"

        ext_val = ext_fields.get(field, None)
        rule_val = rule_fields.get(field, None)
        llm_val = llm_fields.get(field, None)

        if _is_known(ext_val):
            val = ext_val
            src = "extended"
        elif _is_known(rule_val):
            val = rule_val
            src = "rules"
        elif _is_known(llm_val):
            val = llm_val
            src = "llm_cf"
        else:
            val = "Unknown"
            src = "none"

        fused[field] = val
        sources[field] = src

    return {
        "fused_fields": fused,
        "sources": sources,
        "components": {
            "rules": rules_out,
            "extended": ext_out,
            "llm": llm_out,
        },
    }

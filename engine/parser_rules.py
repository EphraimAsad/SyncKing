# engine/parser_rules.py
# ---------------------------------
# Simple regex-based rule parser placeholder

import re

def parse_text_rules(text: str) -> dict:
    """
    Very early stub for rule-based parsing.
    Later we’ll add regex & synonym logic.
    """
    parsed = {}

    # Example (toy pattern)
    if re.search(r"gram[-\s]?positive", text, re.I):
        parsed["Gram Stain"] = "Positive"
    elif re.search(r"gram[-\s]?negative", text, re.I):
        parsed["Gram Stain"] = "Negative"

    # Placeholder: detect oxidase
    if re.search(r"oxidase\s*(\+|positive)", text, re.I):
        parsed["Oxidase"] = "Positive"
    elif re.search(r"oxidase\s*(\-|negative)", text, re.I):
        parsed["Oxidase"] = "Negative"

    return {"parsed_fields": parsed, "source": "rule_parser"}

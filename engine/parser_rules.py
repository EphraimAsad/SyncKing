# engine/parser_rules.py
# ---------------------------------
# Baseline regex/parser rules for common microbiology phrases.
# This is a starter; we’ll expand it iteratively using your gold tests.

import re
from typing import Dict

FERM_SUGARS = [
    "Glucose", "Lactose", "Sucrose", "Maltose", "Mannitol", "Sorbitol",
    "Xylose", "Rhamnose", "Arabinose", "Raffinose", "Trehalose", "Inositol"
]

def _set_result(d: Dict[str, str], field: str, value: str):
    # Don’t overwrite if we already have a confident value
    if field not in d or d[field] == "Unknown":
        d[field] = value

def parse_text_rules(text: str) -> dict:
    """
    Rule-based parsing for frequent/clean patterns.
    Returns {"parsed_fields": {...}, "source": "rule_parser"}.
    """
    t = text.strip()
    parsed: Dict[str, str] = {}

    # --- Gram Stain ---
    if re.search(r"\bgram[-\s]?positive\b", t, re.I):
        _set_result(parsed, "Gram Stain", "Positive")
    if re.search(r"\bgram[-\s]?negative\b", t, re.I):
        _set_result(parsed, "Gram Stain", "Negative")

    # --- Shape (basic) ---
    if re.search(r"\bcocci\b", t, re.I):
        _set_result(parsed, "Shape", "Cocci")
    if re.search(r"\brods?\b", t, re.I):
        _set_result(parsed, "Shape", "Rods")
    if re.search(r"\bbacilli\b", t, re.I):
        _set_result(parsed, "Shape", "Bacilli")
    if re.search(r"\bspiral|spirochete\b", t, re.I):
        _set_result(parsed, "Shape", "Spiral")
    if re.search(r"\bcoccobacilli|short\s+rods?\b", t, re.I):
        _set_result(parsed, "Shape", "Short Rods")

    # --- Catalase / Oxidase / Coagulase / DNase / Urease etc. ---
    simple_tests = [
        "Catalase", "Oxidase", "Coagulase", "DNase", "Urease",
        "Citrate", "Methyl Red", "VP", "H2S", "ONPG",
        "Motility", "Capsule", "Spore Formation", "Nitrate Reduction", "Lipase Test"
    ]
    for test in simple_tests:
        # positive
        if re.search(rf"\b{re.escape(test)}\s*(\+|positive)\b", t, re.I):
            _set_result(parsed, test, "Positive")
        # negative
        if re.search(rf"\b{re.escape(test)}\s*(\-|negative)\b", t, re.I):
            _set_result(parsed, test, "Negative")
        # variable
        if re.search(rf"\b{re.escape(test)}\s*variable\b", t, re.I):
            _set_result(parsed, test, "Variable")

    # --- Haemolysis / Haemolysis Type ---
    if re.search(r"\b(beta|α|alpha|γ|gamma)\s*[- ]?ha?emoly(si|z)is\b", t, re.I):
        _set_result(parsed, "Haemolysis", "Positive")
        if re.search(r"\bbeta\s*[- ]?ha?em", t, re.I):
            _set_result(parsed, "Haemolysis Type", "Beta")
        elif re.search(r"\balpha|α\s*[- ]?ha?em", t, re.I):
            _set_result(parsed, "Haemolysis Type", "Alpha")
        elif re.search(r"\bgamma|γ\s*[- ]?ha?em", t, re.I):
            _set_result(parsed, "Haemolysis Type", "Gamma")
    if re.search(r"\bnon[- ]?ha?emoly", t, re.I):
        _set_result(parsed, "Haemolysis", "Negative")
        _set_result(parsed, "Haemolysis Type", "None")

    # --- NaCl tolerance (>=6%) ---
    if re.search(r"\b(nacl|salt)\s*(tolerant|tolerance)\b.*\b(6|6\.0|7|7\.0)\s*%|up to\s*7\s*%", t, re.I):
        _set_result(parsed, "NaCl Tolerant (>=6%)", "Positive")

    # --- Fermentation summary phrases ---
    # e.g., "ferments glucose, mannitol and sucrose but not lactose"
    ferm_pos = re.findall(r"\bferments?\s+([a-z,\s]+?)(?:\bbut\b|\.|,|;|$)", t, re.I)
    ferm_neg = re.findall(r"\bnot\s+([a-z,\s]+?)(?:\bfermented|\bferments|\butili[sz]ed|\.)", t, re.I)

    def _mark_list(txt: str, value: str):
        for sugar in FERM_SUGARS:
            if re.search(rf"\b{sugar}\b", txt, re.I):
                _set_result(parsed, f"{sugar} Fermentation", value)

    for chunk in ferm_pos:
        _mark_list(chunk, "Positive")
    for chunk in ferm_neg:
        _mark_list(chunk, "Negative")

    # --- Temperatures: "Grows at 37 °C" or ranges in prose (baseline) ---
    # We only catch single temps here for now (gold tests often state 37 °C)
    m = re.search(r"\b(?:grows\s+at|growth\s+at)\s*(\d{1,2})\s*[°º]?\s*c", t, re.I)
    if m:
        # store a single temp; later validator can integrate with range
        _set_result(parsed, "Growth Temperature", f"{m.group(1)}//{m.group(1)}")

    # --- Oxygen Requirement (simple phrases) ---
    if re.search(r"\baerobic\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Aerobic")
    if re.search(r"\banaerobic\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Anaerobic")
    if re.search(r"\bfacultative\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Facultative Anaerobe")
    if re.search(r"\bmicroaerophil(ic|e)\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Microaerophilic")

    # --- Media (very light touch here; LLM or alias table will do more later) ---
    if re.search(r"\bmacconkey\b", t, re.I):
        parsed["Media Grown On"] = "MacConkey Agar"
    if re.search(r"\bblood\s+agar\b", t, re.I):
        parsed["Media Grown On"] = (parsed.get("Media Grown On", "") + "; Blood Agar").strip("; ")
    if re.search(r"\bmannitol\s+salt\s+agar\b|\bMSA\b", t, re.I):
        parsed["Media Grown On"] = (parsed.get("Media Grown On", "") + "; Mannitol Salt Agar").strip("; ")

    return {"parsed_fields": parsed, "source": "rule_parser"}

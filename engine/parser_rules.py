# engine/parser_rules.py
# ------------------------------------------------------------
# Expanded regex rules for higher coverage of biochemical phrases.

import re
from typing import Dict

FERM_SUGARS = [
    "Glucose", "Lactose", "Sucrose", "Maltose", "Mannitol", "Sorbitol",
    "Xylose", "Rhamnose", "Arabinose", "Raffinose", "Trehalose", "Inositol"
]

MEDIA_ALIASES = {
    "mac": "MacConkey Agar",
    "macconkey": "MacConkey Agar",
    "msa": "Mannitol Salt Agar",
    "bap": "Blood Agar",
    "blood agar": "Blood Agar",
    "chocolate": "Chocolate Agar",
    "cled": "CLED Agar"
}

def _set_result(d: Dict[str, str], field: str, value: str):
    if field not in d or d[field] == "Unknown":
        d[field] = value

def _detect_simple(test: str, text: str, parsed: Dict[str, str]):
    if re.search(rf"\b{test}\s*(\+|positive)\b", text, re.I):
        _set_result(parsed, test, "Positive")
    elif re.search(rf"\b{test}\s*(\-|negative)\b", text, re.I):
        _set_result(parsed, test, "Negative")
    elif re.search(rf"\b{test}\s*variable\b", text, re.I):
        _set_result(parsed, test, "Variable")

def parse_text_rules(text: str) -> dict:
    t = text.strip()
    parsed: Dict[str, str] = {}

    # --- Gram Stain ---
    if re.search(r"\bgram[-\s]?positive\b", t, re.I):
        _set_result(parsed, "Gram Stain", "Positive")
    elif re.search(r"\bgram[-\s]?negative\b", t, re.I):
        _set_result(parsed, "Gram Stain", "Negative")

    # --- Shape ---
    if re.search(r"\bcocci\b", t, re.I):
        _set_result(parsed, "Shape", "Cocci")
    if re.search(r"\bcoccobacilli|short\s+rods?\b", t, re.I):
        _set_result(parsed, "Shape", "Short Rods")
    if re.search(r"\brods?\b", t, re.I):
        _set_result(parsed, "Shape", "Rods")
    if re.search(r"\bbacilli\b", t, re.I):
        _set_result(parsed, "Shape", "Bacilli")
    if re.search(r"\bspirochete|spiral\b", t, re.I):
        _set_result(parsed, "Shape", "Spiral")

    # --- Common biochemical tests ---
    simple_tests = [
        "Catalase", "Oxidase", "Coagulase", "DNase", "Urease", "Indole",
        "Citrate", "Methyl Red", "VP", "H2S", "ONPG", "Motility",
        "Capsule", "Spore Formation", "Nitrate Reduction", "Lipase Test"
    ]
    for test in simple_tests:
        _detect_simple(test, t, parsed)

    # --- Haemolysis / Type ---
    if re.search(r"(β|beta)[-\s]?(haemo|hemo)lys", t, re.I):
        _set_result(parsed, "Haemolysis", "Positive")
        _set_result(parsed, "Haemolysis Type", "Beta")
    elif re.search(r"(α|alpha)[-\s]?(haemo|hemo)lys", t, re.I):
        _set_result(parsed, "Haemolysis", "Positive")
        _set_result(parsed, "Haemolysis Type", "Alpha")
    elif re.search(r"(γ|gamma)[-\s]?(haemo|hemo)lys", t, re.I):
        _set_result(parsed, "Haemolysis", "Positive")
        _set_result(parsed, "Haemolysis Type", "Gamma")
    elif re.search(r"non[-\s]?(haemo|hemo)lytic", t, re.I):
        _set_result(parsed, "Haemolysis", "Negative")
        _set_result(parsed, "Haemolysis Type", "None")

    # --- Motility synonyms ---
    if re.search(r"\bmotile|swarming\b", t, re.I):
        _set_result(parsed, "Motility", "Positive")
    if re.search(r"\bnon[- ]?motile|immotile\b", t, re.I):
        _set_result(parsed, "Motility", "Negative")

    # --- Nitrate Reduction special cases ---
    if re.search(r"\bnitrate\s+(?:is\s+)?reduced\b", t, re.I):
        _set_result(parsed, "Nitrate Reduction", "Positive")
    if re.search(r"\bno\s+nitrate\s+reduction\b", t, re.I):
        _set_result(parsed, "Nitrate Reduction", "Negative")

    # --- Fermentation parsing ---
    ferm_pos = re.findall(r"ferments?\s+([a-z,\s]+?)(?:but|except|not|\.)", t, re.I)
    ferm_neg = re.findall(r"(?:but|except)\s+not\s+([a-z,\s]+?)(?:\.)", t, re.I)
    def mark_sugars(txt, value):
        for sugar in FERM_SUGARS:
            if re.search(rf"\b{sugar}\b", txt, re.I):
                _set_result(parsed, f"{sugar} Fermentation", value)
    for chunk in ferm_pos:
        mark_sugars(chunk, "Positive")
    for chunk in ferm_neg:
        mark_sugars(chunk, "Negative")

    # --- NaCl tolerance ---
    if re.search(r"(6(\.5)?|7)\s*%.*(nacl|salt).*tolerant", t, re.I):
        _set_result(parsed, "NaCl Tolerant (>=6%)", "Positive")

    # --- Growth Temperature ---
    m = re.findall(r"(?:grows\s+at|growth\s+at)\s*(\d{1,2})\s*[°º]?\s*c", t, re.I)
    if m:
        low = min(map(int, m))
        high = max(map(int, m))
        _set_result(parsed, "Growth Temperature", f"{low}//{high}")

    # --- Oxygen Requirement ---
    if re.search(r"\bfacultative\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Facultative Anaerobe")
    elif re.search(r"\baerobic\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Aerobic")
    elif re.search(r"\banaerobic\b", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Anaerobic")
    elif re.search(r"\bmicroaerophil", t, re.I):
        _set_result(parsed, "Oxygen Requirement", "Microaerophilic")

    # --- Media detection ---
    found_media = []
    for alias, canon in MEDIA_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", t, re.I):
            found_media.append(canon)
    if found_media:
        _set_result(parsed, "Media Grown On", "; ".join(sorted(set(found_media))))

    return {"parsed_fields": parsed, "source": "rule_parser"}

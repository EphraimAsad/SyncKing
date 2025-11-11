# training/gold_tester.py
# ----------------------------------------------------
# Enhanced tester: audits expected fields not in schema,
# adds DNase/Dnase alias and range-aware Growth Temperature matching.

import json, os, time, csv
from collections import Counter
from typing import Dict, List, Tuple
from engine.schema import SCHEMA, UNKNOWN, normalize_value, is_enum_field
from engine.parser_rules import parse_text_rules

REPORTS_DIR = "reports"
PROPOSALS_PATH = os.path.join("data", "extended_proposals.jsonl")
GOLD_PATH = os.path.join("training", "gold_tests.json")

# --- helpers ---
def load_gold() -> List[Dict]:
    with open(GOLD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _range_overlap(a: str, b: str) -> bool:
    try:
        la, ha = [float(x) for x in a.split("//")]
        lb, hb = [float(x) for x in b.split("//")]
        return not (ha < lb or hb < la)
    except Exception:
        return False

def compare_records(pred: Dict[str, str], exp: Dict[str, str]) -> Tuple[int, int, Dict[str, Tuple[str, str]]]:
    correct, total, errors = 0, 0, {}
    for field, exp_val in exp.items():
        total += 1
        p = pred.get(field, UNKNOWN)
        if field == "Growth Temperature":
            if p != UNKNOWN and exp_val != UNKNOWN and _range_overlap(p, exp_val):
                correct += 1
                continue
        if p == exp_val:
            correct += 1
        else:
            errors[field] = (p, exp_val)
    return correct, total, errors

def append_proposal(record: Dict):
    os.makedirs(os.path.dirname(PROPOSALS_PATH), exist_ok=True)
    with open(PROPOSALS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# --- main ---
def run_gold_tests(mode: str = "rules") -> Dict:
    tests = load_gold()
    ts = time.strftime("%Y%m%d_%H%M%S")

    per_field_counts, per_field_correct, per_field_cov = Counter(), Counter(), Counter()
    unknown_fields, unknown_values = Counter(), Counter()
    expected_unknowns = Counter()
    detailed_rows = []
    cases_with_misses = 0

    for case in tests:
        name, text, expected = case.get("name", ""), case.get("input", ""), case.get("expected", {})

        # normalize expected key aliases
        expected_norm = {}
        for k, v in expected.items():
            k2 = "DNase" if k.lower() == "dnase" else k
            expected_norm[k2] = v
        expected = expected_norm

        out = parse_text_rules(text)
        parsed = out.get("parsed_fields", {})

        # normalize parser output
        normalized_pred = {}
        for field, val in parsed.items():
            if field not in SCHEMA:
                unknown_fields[field] += 1
                append_proposal({
                    "type": "unknown_field",
                    "field": field,
                    "value": val,
                    "case_name": name,
                    "timestamp": ts
                })
                continue
            normalized_pred[field] = normalize_value(field, val)
            if is_enum_field(field):
                allowed = SCHEMA[field].get("allowed", [])
                if normalized_pred[field] not in allowed + [UNKNOWN]:
                    unknown_values[(field, normalized_pred[field])] += 1
                    append_proposal({
                        "type": "unknown_value",
                        "field": field,
                        "value": normalized_pred[field],
                        "allowed": allowed,
                        "case_name": name,
                        "timestamp": ts
                    })

        # audit expected fields not in schema
        for ef in expected.keys():
            if ef not in SCHEMA:
                expected_unknowns[ef] += 1
                append_proposal({
                    "type": "expected_field_not_in_schema",
                    "field": ef,
                    "case_name": name,
                    "timestamp": ts
                })

        correct, total, errors = compare_records(normalized_pred, expected)
        if errors:
            cases_with_misses += 1

        for f in expected.keys():
            per_field_counts[f] += 1
            if f in normalized_pred and normalized_pred[f] != UNKNOWN:
                per_field_cov[f] += 1
            if f not in errors:
                per_field_correct[f] += 1

        detailed_rows.append({
            "name": name,
            "parsed": json.dumps(normalized_pred, ensure_ascii=False),
            "expected": json.dumps(expected, ensure_ascii=False),
            "correct_fields": correct,
            "total_fields": total
        })

    # --- aggregate metrics ---
    per_field_metrics = []
    for f, tot in per_field_counts.items():
        acc = per_field_correct[f] / tot if tot else 0.0
        cov = per_field_cov[f] / tot if tot else 0.0
        per_field_metrics.append({"field": f, "accuracy": round(acc, 4), "coverage": round(cov, 4), "n": tot})
    per_field_metrics.sort(key=lambda x: x["field"])

    micro_acc = sum(per_field_correct.values()) / sum(per_field_counts.values()) if per_field_counts else 0.0

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "mode": mode,
        "timestamp": ts,
        "num_tests": len(tests),
        "micro_accuracy": round(micro_acc, 4),
        "cases_with_misses": cases_with_misses,
        "per_field": per_field_metrics,
        "unknown_fields": dict(unknown_fields),
        "unknown_values": {f"{k[0]}::{k[1]}": v for k, v in unknown_values.items()},
        "expected_unknown_fields": dict(expected_unknowns),
        "proposals_path": PROPOSALS_PATH
    }
    json_path = os.path.join(REPORTS_DIR, f"gold_report_{mode}_{ts}.json")
    csv_fields = os.path.join(REPORTS_DIR, f"gold_fields_{mode}_{ts}.csv")
    csv_cases = os.path.join(REPORTS_DIR, f"gold_cases_{mode}_{ts}.csv")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(csv_fields, "w", newline="", encoding="utf-8") as f:
        import csv
        w = csv.DictWriter(f, fieldnames=["field", "accuracy", "coverage", "n"])
        w.writeheader()
        w.writerows(per_field_metrics)
    with open(csv_cases, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "parsed", "expected", "correct_fields", "total_fields"])
        w.writeheader()
        w.writerows(detailed_rows)

    return {"summary": report, "paths": {"json_report": json_path, "csv_fields": csv_fields, "csv_cases": csv_cases}}

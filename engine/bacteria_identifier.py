# engine/bacteria_identifier.py
# ------------------------------------------------------------
# Core identification engine + blended scoring with extended signals.

import os
import json
import re
import random
from typing import Dict, List, Optional, Tuple

import pandas as pd

from engine.extended_reasoner import score_genera_from_extended

DATA_DIR = "data"
EXT_SCHEMA_PATH = os.path.join(DATA_DIR, "extended_schema.json")


# -----------------------------
# Helper Function
# -----------------------------
def join_with_and(items):
    """Join list into a readable string, using commas and 'and' before last item."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# -----------------------------
# Identification Result Class
# -----------------------------
class IdentificationResult:
    """
    Stores data about a single bacterial genus result and generates reasoning text.
    Now includes optional extended-likelihood and blended confidence.
    """
    def __init__(
        self,
        genus: str,
        total_score: int,
        matched_fields: List[str],
        mismatched_fields: List[str],
        reasoning_factors: Dict[str, str],
        total_fields_evaluated: int,
        total_fields_possible: int,
        extra_notes: str = "",
        extended_likelihood: Optional[float] = None,
        extended_explanation: str = "",
    ):
        self.genus = genus
        self.total_score = total_score
        self.matched_fields = matched_fields
        self.mismatched_fields = mismatched_fields
        self.reasoning_factors = reasoning_factors
        self.total_fields_evaluated = total_fields_evaluated
        self.total_fields_possible = total_fields_possible
        self.extra_notes = extra_notes

        # Extended reasoning
        self.extended_likelihood = extended_likelihood  # 0–1, or None if no extended data
        self.extended_explanation = extended_explanation

    # -----------------------------
    # Confidence Calculations
    # -----------------------------
    def confidence_percent(self) -> int:
        """Confidence based only on tests the user entered."""
        if self.total_fields_evaluated == 0:
            return 0
        return max(
            0,
            min(100, int((self.total_score / self.total_fields_evaluated) * 100)),
        )

    def true_confidence(self) -> int:
        """Confidence based on *all* possible tests (complete database fields)."""
        if self.total_fields_possible == 0:
            return 0
        return max(
            0,
            min(100, int((self.total_score / self.total_fields_possible) * 100)),
        )

    def blended_confidence_raw(self, weight_core: float = 0.7, weight_ext: float = 0.3) -> float:
        """
        Blended confidence:
            core = core-confidence (0–1)
            ext  = extended likelihood (0–1, if available)
        If no extended likelihood, return core.
        """
        core = self.confidence_percent() / 100.0
        if self.extended_likelihood is None:
            return core
        return weight_core * core + weight_ext * self.extended_likelihood

    def blended_confidence_percent(self, weight_core: float = 0.7, weight_ext: float = 0.3) -> int:
        return int(round(self.blended_confidence_raw(weight_core, weight_ext) * 100))

    # -----------------------------
    # Reasoning Paragraph Generator
    # -----------------------------
    def reasoning_paragraph(self, ranked_results=None) -> str:
        """Generate detailed reasoning paragraph with comparison to other genera."""
        if not self.matched_fields:
            return "No significant biochemical or morphological matches were found."

        intro = random.choice(
            [
                "Based on the observed biochemical and morphological traits,",
                "According to the provided test results,",
                "From the available laboratory findings,",
                "Considering the entered reactions and colony traits,",
            ]
        )

        # Key descriptive highlights
        highlights = []
        if "Gram Stain" in self.matched_fields:
            highlights.append(
                f"it is **Gram {self.reasoning_factors.get('Gram Stain', '').lower()}**"
            )
        if "Shape" in self.matched_fields:
            highlights.append(
                f"with a **{self.reasoning_factors.get('Shape', '').lower()}** morphology"
            )
        if "Catalase" in self.matched_fields:
            highlights.append(
                f"and **catalase {self.reasoning_factors.get('Catalase', '').lower()}** activity"
            )
        if "Oxidase" in self.matched_fields:
            highlights.append(
                f"and **oxidase {self.reasoning_factors.get('Oxidase', '').lower()}** reaction"
            )
        if "Oxygen Requirement" in self.matched_fields:
            highlights.append(
                f"which prefers **{self.reasoning_factors.get('Oxygen Requirement', '').lower()}** conditions"
            )

        # Join highlights grammatically
        summary = (
            ", ".join(highlights[:-1]) + " and " + highlights[-1]
            if len(highlights) > 1
            else "".join(highlights)
        )

        # Confidence text (core)
        core_conf = self.confidence_percent()
        confidence_text = (
            "The confidence in this identification based on the entered tests is high."
            if core_conf >= 70
            else "The confidence in this identification based on the entered tests is moderate."
        )

        # Comparative reasoning vs other close results
        comparison = ""
        if ranked_results and len(ranked_results) > 1:
            close_others = ranked_results[1:3]
            other_names = [r.genus for r in close_others]
            if other_names:
                if self.total_score >= close_others[0].total_score:
                    comparison = (
                        f" It is **more likely** than {join_with_and(other_names)} "
                        f"based on stronger alignment in {join_with_and(self.matched_fields[:3])}."
                    )
                else:
                    comparison = (
                        f" It is **less likely** than {join_with_and(other_names)} "
                        f"due to differences in {join_with_and(self.mismatched_fields[:3])}."
                    )

        return f"{intro} {summary}, the isolate most closely resembles **{self.genus}**. {confidence_text}{comparison}"


# -----------------------------
# Bacteria Identifier Engine
# -----------------------------
class BacteriaIdentifier:
    """
    Main engine to match bacterial genus based on biochemical & morphological data.
    Includes:
      - Core rule-based matching vs bacteria_db.xlsx
      - Optional blending with extended signals (signals_catalog.json)
    """

    def __init__(self, db: pd.DataFrame):
        self.db = db.fillna("")
        self.extended_fields = self._load_extended_fields()

    def _load_extended_fields(self) -> List[str]:
        if not os.path.exists(EXT_SCHEMA_PATH):
            return []
        try:
            with open(EXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)
            return list(schema.keys())
        except Exception:
            return []

    # -----------------------------
    # Field Comparison Logic
    # -----------------------------
    def compare_field(self, db_val, user_val, field_name: str) -> int:
        """Compare one test field between database and user input."""
        if not user_val or str(user_val).strip() == "" or str(user_val).lower() == "unknown":
            return 0  # Skip empty or unknown

        db_val = str(db_val).strip().lower()
        user_val = str(user_val).strip().lower()
        hard_exclusions = ["Gram Stain", "Shape", "Spore Formation"]

        # Split entries by separators for multi-value matches
        db_options = re.split(r"[;/]", db_val)
        user_options = re.split(r"[;/]", user_val)
        db_options = [x.strip() for x in db_options if x.strip()]
        user_options = [x.strip() for x in user_options if x.strip()]

        # Handle "variable" logic
        if "variable" in db_options or "variable" in user_options:
            return 0

        # Special handling for Growth Temperature
        if field_name == "Growth Temperature":
            try:
                if "//" in db_val:
                    low, high = [float(x) for x in db_val.split("//")]
                    temp = float(user_val)
                    return 1 if low <= temp <= high else -1
            except Exception:
                return 0

        # Flexible match: partial overlap counts as match
        match_found = any(
            any(u in db_opt or db_opt in u for db_opt in db_options) for u in user_options
        )

        if match_found:
            return 1
        else:
            if field_name in hard_exclusions:
                return -999  # Hard exclusion
            return -1

    # -----------------------------
    # Suggest Next Tests
    # -----------------------------
    def suggest_next_tests(self, top_results: List[IdentificationResult]) -> List[str]:
        """Suggest 3 tests that best differentiate top matches."""
        if len(top_results) < 2:
            return []
        varying_fields = []
        top3 = top_results[:3]

        for field in self.db.columns:
            if field in ["Genus", "Extra Notes", "Colony Morphology"]:
                continue

            field_values = set()
            for r in top3:
                field_values.update(r.matched_fields)
                field_values.update(r.mismatched_fields)

            if len(field_values) > 1:
                varying_fields.append(field)

        random.shuffle(varying_fields)
        return varying_fields[:3]

    # -----------------------------
    # Extended Input Extraction
    # -----------------------------
    def _extract_extended_input(self, user_input: Dict[str, str]) -> Dict[str, str]:
        """
        Extract extended tests (those in extended_schema.json but not part of the core db).
        Only keep Positive/Negative/Variable (ignore Unknown/empty).
        """
        ext_in = {}
        for field in self.extended_fields:
            val = user_input.get(field, "Unknown")
            if isinstance(val, str) and val.lower() in ("positive", "negative", "variable"):
                ext_in[field] = val.capitalize()
        return ext_in

    # -----------------------------
    # Main Identification Routine
    # -----------------------------
    def identify(self, user_input: Dict[str, str]) -> List[IdentificationResult]:
        """Compare user input to database and rank possible genera with blended scoring."""
        results: List[IdentificationResult] = []
        total_fields_possible = len([c for c in self.db.columns if c != "Genus"])

        # 1) Core scoring loop against bacteria_db.xlsx
        for _, row in self.db.iterrows():
            genus = row["Genus"]
            total_score = 0
            matched_fields: List[str] = []
            mismatched_fields: List[str] = []
            reasoning_factors: Dict[str, str] = {}
            total_fields_evaluated = 0

            for field in self.db.columns:
                if field == "Genus":
                    continue

                db_val = row[field]
                user_val = user_input.get(field, "")
                score = self.compare_field(db_val, user_val, field)

                # Count only real inputs for relative confidence
                if user_val and str(user_val).lower() != "unknown":
                    total_fields_evaluated += 1

                if score == -999:
                    total_score = -999
                    break  # Hard exclusion ends comparison

                elif score == 1:
                    total_score += 1
                    matched_fields.append(field)
                    reasoning_factors[field] = user_val

                elif score == -1:
                    total_score -= 1
                    mismatched_fields.append(field)

            # Append valid genus result
            if total_score > -999:
                extra_notes = row.get("Extra Notes", "")
                results.append(
                    IdentificationResult(
                        genus=genus,
                        total_score=total_score,
                        matched_fields=matched_fields,
                        mismatched_fields=mismatched_fields,
                        reasoning_factors=reasoning_factors,
                        total_fields_evaluated=total_fields_evaluated,
                        total_fields_possible=total_fields_possible,
                        extra_notes=extra_notes,
                    )
                )

        if not results:
            return []

        # 2) Suggest next tests for top core results
        top_suggestions = self.suggest_next_tests(results)
        for r in results[:3]:
            r.reasoning_factors["next_tests"] = ", ".join(top_suggestions)

        # 3) Extended likelihoods (if user provided extended tests)
        ext_input = self._extract_extended_input(user_input)
        ext_scores: Dict[str, float] = {}
        ext_explanation = ""

        if ext_input:
            ranked, ext_explanation = score_genera_from_extended(ext_input)
            ext_scores = {g: s for g, s in ranked}

        # Attach extended scores/explanations to each result
        if ext_scores:
            for r in results:
                if r.genus in ext_scores:
                    r.extended_likelihood = ext_scores[r.genus]
                else:
                    # If genus not in signals, treat as neutral (no info)
                    r.extended_likelihood = None
                r.extended_explanation = ext_explanation
        else:
            for r in results:
                r.extended_likelihood = None
                r.extended_explanation = ""

        # 4) Sort results
        if any(r.extended_likelihood is not None for r in results):
            # Sort by blended confidence when extended data is present
            results.sort(key=lambda x: x.blended_confidence_raw(), reverse=True)
        else:
            # Fallback to core total_score
            results.sort(key=lambda x: x.total_score, reverse=True)

        # Return top 10
        return results[:10]

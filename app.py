import streamlit as st
import pandas as pd
import re
import os
import json
from fpdf import FPDF
from datetime import datetime

# ---- ENGINE IMPORTS ----
from engine.bacteria_identifier import BacteriaIdentifier

# ---- STREAMLIT CONFIG ----
st.set_page_config(page_title="BactAI-D Assistant", layout="wide")

# =========================
# DATA LOADING
# =========================
@st.cache_data
def load_data(path, last_modified):
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    return df

# Resolve path (prefer ./data/bacteria_db.xlsx, fallback to ./bacteria_db.xlsx)
primary_path = os.path.join("data", "bacteria_db.xlsx")
fallback_path = os.path.join("bacteria_db.xlsx")
data_path = primary_path if os.path.exists(primary_path) else fallback_path

# Get last modified time (used as cache key so cache invalidates on change)
try:
    last_modified = os.path.getmtime(data_path)
except FileNotFoundError:
    st.error(f"Database file not found at '{primary_path}' or '{fallback_path}'.")
    st.stop()

db = load_data(data_path, last_modified)
eng = BacteriaIdentifier(db)

# Optional: show when the DB was last updated
st.sidebar.caption(
    f"📅 Database last updated: {datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')}"
)

# =========================
# APP HEADER + TABS
# =========================
st.title("🧫 BactAI-D: Intelligent Bacteria Identification Assistant")
st.markdown(
    "Use the tabs below to switch between **manual entry**, **AI parsing**, and "
    "**gold test evaluation & training**."
)

tab_manual, tab_llm, tab_gold = st.tabs(["🔬 Manual Entry", "🧠 LLM Parser", "📚 Gold Tests"])

# =========================
# TAB 1: MANUAL ENTRY
# =========================
with tab_manual:

    # --- FIELD GROUPS ---
    MORPH_FIELDS = [
        "Gram Stain",
        "Shape",
        "Colony Morphology",
        "Media Grown On",
        "Motility",
        "Capsule",
        "Spore Formation",
    ]
    ENZYME_FIELDS = ["Catalase", "Oxidase", "Coagulase", "Lipase Test"]
    SUGAR_FIELDS = [
        "Glucose Fermentation",
        "Lactose Fermentation",
        "Sucrose Fermentation",
        "Maltose Fermentation",
        "Mannitol Fermentation",
        "Sorbitol Fermentation",
        "Xylose Fermentation",
        "Rhamnose Fermentation",
        "Arabinose Fermentation",
        "Raffinose Fermentation",
        "Trehalose Fermentation",
        "Inositol Fermentation",
    ]

    # --- SESSION STATE ---
    if "user_input" not in st.session_state:
        st.session_state.user_input = {}
    if "results" not in st.session_state:
        st.session_state.results = pd.DataFrame()

    # --- RESET TRIGGER HANDLER ---
    if "reset_trigger" in st.session_state and st.session_state["reset_trigger"]:
        for key in list(st.session_state.user_input.keys()):
            st.session_state.user_input[key] = "Unknown"

        for key in list(st.session_state.keys()):
            if key not in ["user_input", "results", "reset_trigger"]:
                if isinstance(st.session_state[key], list):
                    st.session_state[key] = []
                else:
                    st.session_state[key] = "Unknown"

        st.session_state["reset_trigger"] = False
        st.rerun()

    # --- SIDEBAR HEADER ---
    st.sidebar.markdown(
        """
        <div style='background-color:#1565C0; padding:12px; border-radius:10px;'>
            <h3 style='text-align:center; color:white; margin:0;'>🔬 Input Test Results</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    def get_unique_values(field):
        vals = []
        for v in eng.db[field]:
            parts = re.split(r"[;/]", str(v))
            for p in parts:
                clean = p.strip()
                if clean and clean not in vals:
                    vals.append(clean)
        vals.sort()
        return vals

    # --- SIDEBAR INPUTS ---
    with st.sidebar.expander("🧫 Morphological Tests", expanded=True):
        for field in MORPH_FIELDS:
            if field in ["Shape", "Colony Morphology", "Media Grown On"]:
                options = get_unique_values(field)
                selected = st.multiselect(field, options, default=[], key=field)
                st.session_state.user_input[field] = (
                    "; ".join(selected) if selected else "Unknown"
                )
            else:
                st.session_state.user_input[field] = st.selectbox(
                    field,
                    ["Unknown", "Positive", "Negative", "Variable"],
                    index=0,
                    key=field,
                )

    with st.sidebar.expander("🧪 Enzyme Tests", expanded=False):
        for field in ENZYME_FIELDS:
            st.session_state.user_input[field] = st.selectbox(
                field,
                ["Unknown", "Positive", "Negative", "Variable"],
                index=0,
                key=field,
            )

    with st.sidebar.expander("🍬 Carbohydrate Fermentation Tests", expanded=False):
        for field in SUGAR_FIELDS:
            st.session_state.user_input[field] = st.selectbox(
                field,
                ["Unknown", "Positive", "Negative", "Variable"],
                index=0,
                key=field,
            )

    with st.sidebar.expander("🧬 Other Tests", expanded=False):
        for field in db.columns:
            if field in ["Genus"] + MORPH_FIELDS + ENZYME_FIELDS + SUGAR_FIELDS:
                continue
            if field == "Haemolysis Type":
                options = get_unique_values(field)
                selected = st.multiselect(field, options, default=[], key=field)
                st.session_state.user_input[field] = (
                    "; ".join(selected) if selected else "Unknown"
                )
            elif field == "Oxygen Requirement":
                options = get_unique_values(field)
                st.session_state.user_input[field] = st.selectbox(
                    field, ["Unknown"] + options, index=0, key=field
                )
            elif field == "Growth Temperature":
                st.session_state.user_input[field] = st.text_input(
                    field + " (°C)", "", key=field
                )
            else:
                st.session_state.user_input[field] = st.selectbox(
                    field,
                    ["Unknown", "Positive", "Negative", "Variable"],
                    index=0,
                    key=field,
                )

    # --- EXTENDED TESTS (Experimental) ---
    ext_schema_path = os.path.join("data", "extended_schema.json")
    ext_schema = {}
    if os.path.exists(ext_schema_path):
        try:
            with open(ext_schema_path, "r", encoding="utf-8") as f:
                ext_schema = json.load(f)
        except Exception:
            ext_schema = {}

    # CORE FIELDS (same list as in parser_ext)
    CORE_FIELDS = {
        "Genus","Species","Gram Stain","Shape","Colony Morphology","Haemolysis","Haemolysis Type",
        "Motility","Capsule","Spore Formation","Growth Temperature","Oxygen Requirement",
        "Media Grown On","Catalase","Oxidase","Coagulase","DNase","Urease","Citrate","Methyl Red",
        "VP","H2S","ONPG","Nitrate Reduction","Lipase Test","NaCl Tolerant (>=6%)",
        "Lysine Decarboxylase","Ornitihine Decarboxylase","Arginine dihydrolase",
        "Gelatin Hydrolysis","Esculin Hydrolysis","Glucose Fermentation","Lactose Fermentation",
        "Sucrose Fermentation","Mannitol Fermentation","Sorbitol Fermentation",
        "Maltose Fermentation","Xylose Fermentation","Rhamnose Fermentation",
        "Arabinose Fermentation","Raffinose Fermentation","Trehalose Fermentation",
        "Inositol Fermentation"
    }

    extended_enum_fields = [
        f_name
        for f_name, meta in ext_schema.items()
        if (
            isinstance(meta, dict)
            and meta.get("value_type") == "enum_PNV"
            and f_name not in CORE_FIELDS     # <-- prevent core duplicates
        )
    ]


    if extended_enum_fields:
        with st.sidebar.expander("🧪 Extended Tests (Experimental)", expanded=False):
            for field in sorted(extended_enum_fields):
                st.session_state.user_input[field] = st.selectbox(
                    field,
                    ["Unknown", "Positive", "Negative", "Variable"],
                    index=0,
                    key=field,
                )

    # --- RESET BUTTON ---
    if st.sidebar.button("🔄 Reset All Inputs"):
        st.session_state["reset_trigger"] = True
        st.rerun()

    # --- IDENTIFY BUTTON ---
    if st.sidebar.button("🔍 Identify"):
        with st.spinner("Analyzing results..."):
            results = eng.identify(st.session_state.user_input)
            if not results:
                st.error("No matches found.")
            else:
                results_df = pd.DataFrame(
                    [
                        [
                            r.genus,
                            f"{r.confidence_percent()}%",
                            f"{r.true_confidence()}%",
                            f"{r.blended_confidence_percent()}%",
                            r.reasoning_paragraph(results),
                            r.extended_explanation or "",
                            r.reasoning_factors.get("next_tests", ""),
                            r.extra_notes,
                        ]
                        for r in results
                    ],
                    columns=[
                        "Genus",
                        "Confidence",
                        "True Confidence (All Tests)",
                        "Blended Confidence",
                        "Reasoning",
                        "Extended Evidence",
                        "Next Tests",
                        "Extra Notes",
                    ],
                )
                st.session_state.results = results_df

    # --- DISPLAY RESULTS ---
    if not st.session_state.results.empty:
        st.info(
            "Core percentages are based upon options entered. "
            "Blended confidence also uses extended tests when provided. "
            "True confidence percentage is based on all database fields."
        )
        for _, row in st.session_state.results.iterrows():
            blended_value = int(row["Blended Confidence"].replace("%", ""))
            confidence_color = (
                "🟢" if blended_value >= 75 else "🟡" if blended_value >= 50 else "🔴"
            )
            header = (
                f"**{row['Genus']}** — {confidence_color} "
                f"Blended: {row['Blended Confidence']} (Core: {row['Confidence']})"
            )
            with st.expander(header):
                st.markdown(f"**Reasoning (Core Tests):** {row['Reasoning']}")
                if row["Extended Evidence"]:
                    st.markdown(
                        f"**Extended Evidence (Experimental):**\n\n"
                        f"{row['Extended Evidence']}"
                    )
                st.markdown(
                    f"**Top 3 Next Tests to Differentiate:** {row['Next Tests']}"
                )
                st.markdown(
                    f"**True Confidence (All Tests):** {row['True Confidence (All Tests)']}"
                )
                if row["Extra Notes"]:
                    st.markdown(f"**Notes:** {row['Extra Notes']}")

    # --- PDF EXPORT ---
    def export_pdf(results_df, user_input):
        def safe_text(text):
            """Convert text to Latin-1 safe characters."""
            text = str(text).replace("•", "-").replace("—", "-").replace("–", "-")
            return text.encode("latin-1", "replace").decode("latin-1")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "BactAI-d Identification Report", ln=True, align="C")

        pdf.set_font("Helvetica", "", 11)
        pdf.cell(
            0,
            8,
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ln=True,
        )
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Entered Test Results:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for k, v in user_input.items():
            pdf.multi_cell(0, 6, safe_text(f"- {k}: {v}"))

        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Top Possible Matches:", ln=True)
        pdf.set_font("Helvetica", "", 10)

        for _, row in results_df.iterrows():
            pdf.multi_cell(
                0,
                7,
                safe_text(
                    f"- {row['Genus']} — Blended: {row['Blended Confidence']} "
                    f"(Core: {row['Confidence']}; True: {row['True Confidence (All Tests)']})"
                ),
            )
            pdf.multi_cell(0, 6, safe_text(f"  Reasoning: {row['Reasoning']}"))
            if row["Extended Evidence"]:
                pdf.multi_cell(
                    0,
                    6,
                    safe_text(f"  Extended Evidence: {row['Extended Evidence']}"),
                )
            if row["Next Tests"]:
                pdf.multi_cell(
                    0,
                    6,
                    safe_text(f"  Next Tests: {row['Next Tests']}"),
                )
            if row["Extra Notes"]:
                pdf.multi_cell(
                    0,
                    6,
                    safe_text(f"  Notes: {row['Extra Notes']}"),
                )
            pdf.ln(3)

        pdf.output("BactAI-d_Report.pdf")
        return "BactAI-d_Report.pdf"

    if not st.session_state.results.empty:
        if st.button("📄 Export Results to PDF"):
            pdf_path = export_pdf(st.session_state.results, st.session_state.user_input)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download PDF", f, file_name="BactAI-d_Report.pdf"
                )

# =========================
# TAB 2: LLM PARSER (unchanged from previous stage except for extended buttons)
# =========================
with tab_llm:
    st.info(
        "Paste a microbiology description. We'll parse with rules + extended tests, "
        "then infer likely genera from extended evidence."
    )
    user_text = st.text_area("Paste microbiology description here:")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("Parse (Rule Parser)"):
            from engine.parser_rules import parse_text_rules
            result = parse_text_rules(user_text or "")
            st.subheader("Rule Parser Output")
            st.json(result)

    with col_b:
        if st.button("Parse (Extended Tests)"):
            from engine.parser_ext import parse_text_extended
            result = parse_text_extended(user_text or "")
            st.subheader("Extended Parser Output")
            st.json(result)

    with col_c:
        if st.button("Infer Genera (Extended Signals)"):
            from engine.parser_ext import parse_text_extended
            from engine.extended_reasoner import score_genera_from_extended

            ext = parse_text_extended(user_text or "")
            parsed_ext = ext.get("parsed_fields", {})
            ranked, explain = score_genera_from_extended(parsed_ext)
            st.subheader("Genus Likelihoods (Extended)")
            st.write(explain)
            if ranked:
                st.table(pd.DataFrame(ranked[:10], columns=["Genus", "Score"]))
            else:
                st.caption(
                    "No signal available (try training first or providing a description with extended tests)."
                )
    with col_d:
    if st.button("Parse with LLM (DeepSeek)"):
        from engine.parser_llm import parse_text_llm
        result = parse_text_llm(user_text or "")
        st.subheader("LLM Parser Output")
        st.json(result)

# =========================
# TAB 3: GOLD TESTS (identical to your Stage 5 version)
# =========================
with tab_gold:
    st.subheader("Gold Standard Evaluation")
    st.write(
        "Runs all gold tests, computes field accuracy & coverage, and logs unknown fields/values to "
        "`data/extended_proposals.jsonl` for later review/promotion."
    )

    mode = st.selectbox("Parser Mode", ["rules"], index=0)

    if st.button("Run Gold Tests"):
        with st.spinner("Evaluating gold tests..."):
            from training.gold_tester import run_gold_tests

            result = run_gold_tests(mode=mode)

        st.success("Done!")
        st.subheader("Summary")
        st.json(result["summary"])

        paths = result.get("paths", {})
        for label, p in paths.items():
            try:
                with open(p, "rb") as f:
                    st.download_button(
                        f"⬇️ Download {label}",
                        f,
                        file_name=os.path.basename(p),
                    )
            except Exception:
                st.caption(f"Could not open: {p}")

        st.caption(
            f"Proposals (unknown fields/values) appended to: `{result['summary']['proposals_path']}`"
        )

    st.markdown("---")
    st.subheader("Auto-learning from Gold Tests")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧬 Train from Gold Tests"):
            with st.spinner(
                "Training from gold tests (updating extended schema, alias maps, and signals)..."
            ):
                from training.gold_trainer import train_from_gold

                out = train_from_gold()
            st.success("Training complete.")
            st.json(out)

    with col2:
        if st.button("⬆️ Commit learned files to GitHub"):
            with st.spinner("Pushing updates to GitHub..."):
                from training.repo_sync import push_updates_to_github

                paths = [
                    "data/extended_schema.json",
                    "data/alias_maps.json",
                    "data/signals_catalog.json",
                ]
                result = push_updates_to_github(
                    paths,
                    commit_message="train: update extended schema, aliases, signals from gold tests",
                )
            st.success("Pushed.")
            st.json(result)

# =========================
# FOOTER
# =========================
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center; font-size:14px;'>Created by <b>Zain</b> | www.linkedin.com/in/zain-asad-1998EPH</div>",
    unsafe_allow_html=True,
)



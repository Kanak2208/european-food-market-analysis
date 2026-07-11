"""
app.py — Nutri-Score Predictor (Streamlit)
==================================================================
A live tool: enter a product's nutrition facts, get its predicted
Nutri-Score grade (A–E) from the XGBoost model trained in the project.

Run it:
    pip install streamlit xgboost pandas numpy
    streamlit run app.py

Needs data/products_features.csv (from notebook 02) in a data/ folder
next to this file. On first launch it trains the model once (cached),
then predictions are instant.
==================================================================
"""
import numpy as np
import pandas as pd
from pathlib import Path
import streamlit as st
from xgboost import XGBClassifier

# ---- config -------------------------------------------------------
FEATURES = [
    "energy_kcal_100g", "sugars_100g", "fat_100g", "saturated_fat_100g",
    "salt_100g", "proteins_100g", "fiber_100g", "nova_group", "additives_n",
    "sugar_to_energy", "protein_to_energy", "good_minus_bad",
    "is_high_sugar", "is_high_salt", "is_high_sat_fat", "is_ultra_processed",
]
LABELS = ["A", "B", "C", "D", "E"]
GRADE_COLOR = {"A": "#038141", "B": "#85BB2F", "C": "#FECB02", "D": "#EE8100", "E": "#E63E11"}
GRADE_TEXT = {"A": "Healthiest", "B": "Good", "C": "Moderate", "D": "Poor", "E": "Least healthy"}

DATA = Path("data") if Path("data/products_features.csv").exists() else Path("../data")
CSV = DATA / "products_features.csv"


# ---- model (trained once, then cached) ----------------------------
@st.cache_resource(show_spinner="Training the model (first run only)…")
def load_model():
    df = pd.read_csv(CSV)
    m = df[df["is_trainable"]].copy()
    X = m[FEATURES].astype(float)
    y = m["grade_encoded"].astype(int)
    model = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.1,
        subsample=0.9, colsample_bytree=0.9,
        objective="multi:softprob", num_class=5,
        eval_metric="mlogloss", random_state=42, n_jobs=-1,
    )
    model.fit(X, y)
    return model


# ---- feature engineering (must match notebook 02) ----------------
def build_features(energy, sugars, fat, sat_fat, salt, proteins, fiber, nova, additives):
    e = energy if energy > 0 else np.nan
    row = {
        "energy_kcal_100g": energy, "sugars_100g": sugars, "fat_100g": fat,
        "saturated_fat_100g": sat_fat, "salt_100g": salt, "proteins_100g": proteins,
        "fiber_100g": fiber, "nova_group": nova, "additives_n": additives,
        "sugar_to_energy": (sugars / e) if e == e else np.nan,
        "protein_to_energy": (proteins / e) if e == e else np.nan,
        "good_minus_bad": proteins + fiber - sugars - sat_fat,
        "is_high_sugar": int(sugars > 22.5),
        "is_high_salt": int(salt > 1.5),
        "is_high_sat_fat": int(sat_fat > 5.0),
        "is_ultra_processed": int(nova == 4),
    }
    return pd.DataFrame([row])[FEATURES].astype(float)


# ---- UI -----------------------------------------------------------
st.set_page_config(page_title="Nutri-Score Predictor", page_icon="🥗", layout="centered")
st.title("🥗 Nutri-Score Predictor")
st.caption("Enter a product's nutrition facts (per 100 g). The XGBoost model predicts its "
           "health grade A–E — the same model from the European Food Market Analysis, ~85.6% accurate.")

if not CSV.exists():
    st.error("Couldn't find data/products_features.csv. Run notebook 02 first, and place this app "
             "so that data/products_features.csv sits next to it.")
    st.stop()

model = load_model()

st.subheader("Nutrition per 100 g")
c1, c2 = st.columns(2)
with c1:
    energy = st.number_input("Energy (kcal)", 0.0, 900.0, 250.0, 5.0)
    sugars = st.number_input("Sugars (g)", 0.0, 100.0, 10.0, 0.5)
    fat = st.number_input("Fat (g)", 0.0, 100.0, 10.0, 0.5)
    sat_fat = st.number_input("Saturated fat (g)", 0.0, 100.0, 3.0, 0.5)
with c2:
    salt = st.number_input("Salt (g)", 0.0, 20.0, 0.5, 0.1)
    proteins = st.number_input("Proteins (g)", 0.0, 100.0, 5.0, 0.5)
    fiber = st.number_input("Fibre (g)", 0.0, 50.0, 2.0, 0.5)
    additives = st.number_input("Number of additives", 0, 30, 1, 1)

nova = st.select_slider("NOVA processing group (1 = unprocessed … 4 = ultra-processed)",
                        options=[1, 2, 3, 4], value=3)

if st.button("Predict grade", type="primary", use_container_width=True):
    x = build_features(energy, sugars, fat, sat_fat, salt, proteins, fiber, nova, additives)
    pred = int(model.predict(x)[0])
    proba = model.predict_proba(x)[0]
    grade = LABELS[pred]

    st.markdown(
        f"<div style='background:{GRADE_COLOR[grade]};border-radius:14px;padding:22px;text-align:center;margin-top:10px'>"
        f"<div style='color:white;font-size:64px;font-weight:800;line-height:1'>{grade}</div>"
        f"<div style='color:white;font-size:18px;margin-top:6px'>{GRADE_TEXT[grade]}</div></div>",
        unsafe_allow_html=True,
    )
    st.write("")
    st.caption(f"Model confidence: {proba[pred]*100:.0f}%")
    st.bar_chart(pd.DataFrame({"probability": proba}, index=LABELS))

    with st.expander("What drove this?"):
        st.write(
            f"- **Sugar {sugars} g** → {'above' if sugars > 22.5 else 'below'} the 22.5 g 'high' threshold\n"
            f"- **Salt {salt} g** → {'above' if salt > 1.5 else 'below'} the 1.5 g 'high' threshold\n"
            f"- **Saturated fat {sat_fat} g** → {'above' if sat_fat > 5 else 'below'} the 5 g 'high' threshold\n"
            f"- **NOVA {nova}** → {'ultra-processed' if nova == 4 else 'not ultra-processed'}\n\n"
            "Sugar, salt and saturated fat are the model's strongest predictors — matching the real Nutri-Score."
        )

st.divider()
st.caption("Part of the European Food Market Analysis capstone · model trained on ~23k products with a known grade.")
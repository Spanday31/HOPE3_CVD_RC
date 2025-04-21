import streamlit as st
import os
import math
import pandas as pd
import plotly.graph_objects as go
import logging
from io import BytesIO
from docx import Document

# ── Setup Logging for Analytics ─────────────────────────────────────────────────
logging.basicConfig(filename='analytics.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')

# ── Page Config & Custom CSS ─────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="SMART CVD Risk Reduction")
st.markdown('''<style>
.header { background:#f7f7f7; padding:10px; text-align:center; }
.card { background:#fff; padding:15px; margin-bottom:15px; border-radius:8px;
        box-shadow:0 1px 3px rgba(0,0,0,0.1); }
</style>''', unsafe_allow_html=True)

# ── Header with Logo ─────────────────────────────────────────────────────────
st.markdown('<div class="header">', unsafe_allow_html=True)
if os.path.exists("logo.png"):
    st.image("logo.png", width=600)
else:
    st.warning("⚠️ Logo not found — upload 'logo.png'")
st.markdown('</div>', unsafe_allow_html=True)

# ── Initialize session state for profile ─────────────────────────────────────
if 'age' not in st.session_state:
    st.session_state.update({
        'age': 60, 'sex': 'Male', 'weight': 75.0, 'height': 170.0,
        'smoker': False, 'diabetes': False, 'egfr': 90,
        'tc': 5.2, 'hdl': 1.3, 'ldl0': 3.0, 'crp': 2.5,
        'hba1c': 7.0, 'tg': 1.2,
        'pre_stat': 'None', 'pre_ez': False, 'pre_bemp': False,
        'new_stat': 'None', 'new_ez': False, 'new_bemp': False,
        'sbp': 140
    })

# ── Evidence Mapping ─────────────────────────────────────────────────────────
TRIALS = {
    "Atorvastatin 80 mg": ("CTT meta-analysis", "https://pubmed.ncbi.nlm.nih.gov/20167315/"),
    "Rosuvastatin 20 mg": ("CTT meta-analysis", "https://pubmed.ncbi.nlm.nih.gov/20167315/"),
    "Ezetimibe 10 mg":     ("IMPROVE-IT",         "https://pubmed.ncbi.nlm.nih.gov/26405142/"),
    "Bempedoic acid":      ("CLEAR Outcomes",     "https://pubmed.ncbi.nlm.nih.gov/35338941/"),
    "PCSK9 inhibitor":     ("FOURIER",            "https://pubmed.ncbi.nlm.nih.gov/28436927/"),
    "Inclisiran":          ("ORION-10",           "https://pubmed.ncbi.nlm.nih.gov/32302303/"),
    "Icosapent ethyl":     ("REDUCE-IT",          "https://pubmed.ncbi.nlm.nih.gov/31141850/"),
    "Semaglutide":         ("STEP",               "https://pubmed.ncbi.nlm.nih.gov/34499685/")
}

# ── Utility & Risk Functions ─────────────────────────────────────────────────
def calculate_ldl_projection(baseline_ldl, pre_list, new_list):
    E = {
        "Atorvastatin 80 mg": 0.50,
        "Rosuvastatin 20 mg": 0.55,
        "Ezetimibe 10 mg":     0.20,
        "Bempedoic acid":      0.18,
        "PCSK9 inhibitor":     0.60,
        "Inclisiran":          0.55
    }
    ldl = baseline_ldl
    for drug in pre_list + new_list:
        if drug in E:
            ldl *= (1 - E[drug])
    return max(ldl, 0.5)

def estimate_10y_risk(age, sex, sbp, tc, hdl, smoker, diabetes, egfr, crp, vasc):
    sex_v = 1 if sex == "Male" else 0
    smoke_v = 1 if smoker else 0
    dm_v = 1 if diabetes else 0
    crp_l = math.log(crp + 1)
    lp = (0.064 * age + 0.34 * sex_v + 0.02 * sbp + 0.25 * tc
          -0.25 * hdl + 0.44 * smoke_v + 0.51 * dm_v
          -0.2 * (egfr / 10) + 0.25 * crp_l + 0.4 * vasc)
    raw = 1 - 0.900 ** math.exp(lp - 5.8)
    return round(min(raw * 100, 95.0), 1)

def convert_5yr(r10):
    p = min(r10, 95.0) / 100
    return round(min((1 - (1 - p) ** 0.5) * 100, 95.0), 1)

def estimate_lifetime_risk(age, r10):
    years = max(85 - age, 0)
    p10 = min(r10, 95.0) / 100
    annual = 1 - (1 - p10) ** (1 / 10)
    return round(min((1 - (1 - annual) ** years) * 100, 95.0), 1)

def fmt_pct(x): return f"{x:.1f}%"
def fmt_pp(x):  return f"{x:.1f} pp"

# ── UI Flow ─────────────────────────────────────────────────────────────────
step = st.sidebar.radio("Go to Step", ["1: Profile", "2: Labs", "3: Therapies", "4: Results"])

if step == "1: Profile":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    age = st.number_input("Age (years)", 30, 90, key='age')
    sex = st.radio("Sex", ["Male", "Female"], key='sex')
    weight = st.number_input("Weight (kg)", 40.0, 200.0, key='weight')
    height = st.number_input("Height (cm)", 140.0, 210.0, key='height')
    bmi = weight / ((height / 100) ** 2)
    st.write(f"**BMI:** {bmi:.1f} kg/m²")
    smoker = st.checkbox("Current smoker", key='smoker')
    diabetes = st.checkbox("Diabetes", key='diabetes')
    egfr = st.slider("eGFR (mL/min/1.73 m²)", 15, 120, key='egfr')
    st.markdown('</div>', unsafe_allow_html=True)

elif step == "2: Labs":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tc = st.number_input("Total Cholesterol (mmol/L)", 2.0, 10.0, key='tc')
    hdl = st.number_input("HDL‑C (mmol/L)", 0.5, 3.0, key='hdl')
    ldl0 = st.number_input("Baseline LDL‑C (mmol/L)", 0.5, 6.0, key='ldl0')
    crp = st.number_input("hs‑CRP (mg/L)", 0.1, 20.0, key='crp')
    hba1c = st.number_input("HbA₁c (%)", 4.0, 14.0, key='hba1c')
    tg = st.number_input("Triglycerides (mmol/L)", 0.3, 5.0, key='tg')
    st.markdown('</div>', unsafe_allow_html=True)

elif step == "3: Therapies":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    pre_stat = st.selectbox("Pre‑admission Statin", ["None", "Atorvastatin 80 mg", "Rosuvastatin 20 mg"], key='pre_stat')
    pre_ez = st.checkbox("Pre‑admission Ezetimibe", key='pre_ez')
    pre_bemp = st.checkbox("Pre‑admission Bempedoic acid", key='pre_bemp')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    new_stat = st.selectbox("Statin change", ["None", "Atorvastatin 80 mg", "Rosuvastatin 20 mg"], key='new_stat')
    new_ez = st.checkbox("Add Ezetimibe", key='new_ez')
    new_bemp = st.checkbox("Add Bempedoic acid", key='new_bemp')
    post_ldl = calculate_ldl_projection(
        ldl0,
        [st.session_state.pre_stat] + (["Ezetimibe 10 mg"] if st.session_state.pre_ez else []) + (["Bempedoic acid"] if st.session_state.pre_bemp else []),
        [st.session_state.new_stat] + (["Ezetimibe 10 mg"] if st.session_state.new_ez else []) + (["Bempedoic acid"] if st.session_state.new_bemp else [])
    )
    pcsk9 = st.checkbox("PCSK9 inhibitor", disabled=(post_ldl <= 1.8), key='pcsk9')
    inclisiran = st.checkbox("Inclisiran", disabled=(post_ldl <= 1.8), key='inclisiran')
    st.markdown('</div>', unsafe_allow_html=True)

elif step == "4: Results":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    sbp = st.number_input("Current SBP (mmHg)", 90, 200, key='sbp')
    r10 = estimate_10y_risk(
        st.session_state.age, st.session_state.sex, sbp,
        st.session_state.tc, st.session_state.hdl, st.session_state.smoker,
        st.session_state.diabetes, st.session_state.egfr,
        st.session_state.crp, sum([st.session_state.pre_stat != "None", st.session_state.pre_ez, st.session_state.pre_bemp])
    )
    r5 = convert_5yr(r10)
    rlt = estimate_lifetime_risk(st.session_state.age, r10)
    lifetime_display = "N/A" if st.session_state.age >= 85 else fmt_pct(rlt)
    st.write(f"5‑yr: **{fmt_pct(r5)}**, 10‑yr: **{fmt_pct(r10)}**, Lifetime: **{lifetime_display}**")
    fig = go.Figure(go.Bar(
        x=["5‑yr","10‑yr","Lifetime"],
        y=[r5, r10, rlt if st.session_state.age < 85 else None],
        marker_color=["#f39c12","#e74c3c","#2ecc71"]
    ))
    fig.update_layout(yaxis_title="Risk (%)", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
    arr10 = r10 - rlt if st.session_state.age < 85 else None
    rrr10 = round(arr10 / r10 * 100, 1) if arr10 else None
    st.write(f"ARR (10y): **{fmt_pp(arr10) if arr10 else 'N/A'}**, RRR (10y): **{fmt_pct(rrr10) if rrr10 else 'N/A'}**")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("Created by Samuel Panday — 21/04/2025")
st.markdown("PRIME team, King's College Hospital")
st.markdown("For informational purposes; not a substitute for clinical advice.")

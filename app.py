# app.py
# Run:
#   pip install streamlit
#   python -m streamlit run app.py

import re
import math
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# Helpers (formatting + templating)
# ============================================================
def fmt_money(x: float) -> str:
    x = float(x or 0)
    return f"${x:,.0f}"


def fmt_money_dp(x: float, dp: int = 2) -> str:
    x = float(x or 0)
    return f"${x:,.{dp}f}"


def fmt_pct_ratio(x: float, dp: int = 1) -> str:
    # x is a ratio (0.117 -> 11.7)
    return f"{x * 100:.{dp}f}"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def replace_tokens(svg: str, mapping: dict) -> str:
    def repl(match):
        key = match.group(1).strip()
        return str(mapping.get(key, f"{{{{{key}}}}}"))

    return re.sub(r"\{\{([^}]+)\}\}", repl, svg)


# ============================================================
# Core maths
# ============================================================
def to_monthly(amount: float, freq: str) -> float:
    if freq == "weekly":
        return amount * 52 / 12
    if freq == "fortnightly":
        return amount * 26 / 12
    return amount


def term_years_auto(car_age_now: float) -> float:
    # Heuristic guidance aligned with the framework
    if car_age_now <= 2:
        return 5.0
    if car_age_now <= 7:
        return 4.0
    return 3.0


def amortised_repayment_monthly(loan_amount: float, apr: float, term_years: float, balloon: float) -> float:
    """
    Governing equation (standard amortising loan with optional balloon):

    r = APR / 12
    n = term_years * 12
    PV(balloon) = balloon / (1+r)^n
    P_eff = loan_amount - PV(balloon)

    repayment = P_eff * [ r(1+r)^n / ((1+r)^n - 1) ]

    If APR = 0, repayment = (loan_amount - balloon) / n
    """
    loan_amount = max(0.0, float(loan_amount))
    balloon = max(0.0, float(balloon))
    n = int(round(term_years * 12))
    if n <= 0 or loan_amount <= 0:
        return 0.0

    r = (apr / 100.0) / 12.0
    if r == 0:
        p_eff = max(0.0, loan_amount - balloon)
        return p_eff / n

    pv_balloon = balloon / ((1 + r) ** n)
    p_eff = max(0.0, loan_amount - pv_balloon)

    num = r * ((1 + r) ** n)
    den = ((1 + r) ** n) - 1
    if den == 0:
        return 0.0
    return p_eff * (num / den)


def totals_from_repayment(loan_amount: float, repayment: float, term_years: float, balloon: float) -> tuple[float, float]:
    n = int(round(term_years * 12))
    total_paid = repayment * n + balloon
    total_interest = total_paid - loan_amount
    return total_paid, total_interest


# ============================================================
# Zones + colours
# ============================================================
COL_GREEN = "#2E7D32"
COL_AMBER = "#C7921C"
COL_RED = "#C62828"


def zone_s1(repayment_ratio: float) -> tuple[str, str]:
    # repayment_ratio is monthly repayment / monthly gross income
    p = repayment_ratio * 100
    if p <= 10:
        return "Very safe", COL_GREEN
    if p <= 15:
        return "Safe", COL_GREEN
    if p <= 20:
        return "Risky", COL_AMBER
    return "High risk", COL_RED


def zone_s2(exposure: float) -> tuple[str, str]:
    # exposure is loan_amount / annual gross income
    p = exposure * 100
    if p <= 30:
        return "Strong", COL_GREEN
    if p <= 40:
        return "Acceptable", COL_GREEN
    if p <= 50:
        return "Stretch", COL_AMBER
    return "Unsafe", COL_RED


def zone_s3(price_ratio: float) -> tuple[str, str]:
    # price_ratio is car_price / annual gross income
    p = price_ratio * 100
    if p <= 35:
        return "Conservative", COL_GREEN
    if p <= 50:
        return "Upper safe", COL_GREEN
    if p < 70:
        return "Elevated risk", COL_AMBER
    return "Stress zone", COL_RED


def zone_s4(age_end: float) -> tuple[str, str]:
    # simple reliability-alignment heuristic
    if age_end <= 10:
        return "Aligned", COL_GREEN
    if age_end <= 12:
        return "Borderline", COL_AMBER
    return "Misaligned", COL_RED


def zone_s5(apr: float) -> tuple[str, str]:
    if apr <= 7:
        return "Prime", COL_GREEN
    if apr <= 10:
        return "Normal", COL_GREEN
    if apr <= 15:
        return "Risk-priced", COL_AMBER
    return "High-risk", COL_RED


def zone_s6(buffer_months: float) -> tuple[str, str]:
    if buffer_months >= 6:
        return "Strong", COL_GREEN
    if buffer_months >= 3:
        return "Minimum", COL_AMBER
    return "High risk", COL_RED


def zone_s7(all_in_ratio: float) -> tuple[str, str]:
    p = all_in_ratio * 100
    if p <= 20:
        return "Sustainable", COL_GREEN
    if p <= 25:
        return "Stress zone", COL_AMBER
    return "Unsafe", COL_RED


# ============================================================
# Geometry mapping for SVG
# ============================================================
def needle_angle_from_pct(pct: float, pct_max: float) -> float:
    # maps 0..pct_max to -90..+90 degrees
    pct = clamp(pct, 0.0, pct_max)
    return -90 + (pct / pct_max) * 180


def thermometer_fill(exposure_pct: float) -> tuple[float, float]:
    # bar from y=320 to y=510 (height=190)
    top_y = 320.0
    height = 190.0
    pct = clamp(exposure_pct, 0.0, 60.0)  # clamp for visual stability
    fill_h = height * (pct / 60.0)
    fill_y = top_y + (height - fill_h)
    return fill_y, fill_h


def band_marker_x(pct: float) -> tuple[float, float]:
    # band starts at x=82, width=356
    x0 = 82.0
    w = 356.0
    pct = clamp(pct, 0.0, 80.0)
    x = x0 + w * (pct / 80.0)
    fill_w = w * (pct / 80.0)
    return x, fill_w


def timeline_fill(age_end: float) -> float:
    # timeline width=356, map 0..15 years
    w = 356.0
    age_end = clamp(age_end, 0.0, 15.0)
    return w * (age_end / 15.0)


def jar_fill(buffer_months: float) -> tuple[float, float]:
    # jar from y=1000 to y=1130 (height=130)
    top_y = 1000.0
    height = 130.0
    m = clamp(buffer_months, 0.0, 6.0)
    fill_h = height * (m / 6.0)
    fill_y = top_y + (height - fill_h)
    return fill_y, fill_h


# ============================================================
# Refined SVG template:
# - Adds short “what this shows” text per section
# - Fixes section 1 needle collision by moving gauge centre right
# ============================================================
SVG_TEMPLATE = r"""
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1024 1536"
     preserveAspectRatio="xMidYMid meet"
     style="width:100%; height:auto; display:block;">
  <defs>
    <style>
      .bg { fill: #F4F7FB; }
      .card { fill: #FFFFFF; stroke: #D6DEE9; stroke-width: 2; }
      .title { font: 800 40px Arial, sans-serif; fill: #0E2A47; letter-spacing: 1px; }
      .subtitle { font: 400 22px Arial, sans-serif; fill: #234B72; }

      .sectionTitle { font: 800 20px Arial, sans-serif; fill: #FFFFFF; }
      .sectionTitleBg { fill: #0F3556; }

      .label { font: 700 18px Arial, sans-serif; fill: #0E2A47; }
      .muted { font: 400 16px Arial, sans-serif; fill: #5D728A; }
      .micro { font: 400 14px Arial, sans-serif; fill: #5D728A; }
      .big { font: 800 30px Arial, sans-serif; fill: #0E2A47; }
      .zone { font: 800 18px Arial, sans-serif; fill: #FFFFFF; }
    </style>
  </defs>

  <rect class="bg" x="0" y="0" width="1024" height="1536" rx="28"/>

  <text class="title" x="512" y="88" text-anchor="middle">SMART CAR LOAN FRAMEWORK</text>
  <text class="subtitle" x="512" y="124" text-anchor="middle">Live ratios (Australia) • Minimal inputs</text>

  <rect x="60" y="154" width="904" height="54" rx="14" fill="{{headline_color}}"/>
  <text class="zone" x="88" y="191">Resilience: {{headline_resilience}}  •  Main driver: {{headline_driver}}</text>

  <!-- SECTION 1 -->
  <g id="section1">
    <rect class="card" x="60" y="240" width="420" height="310" rx="18"/>
    <rect class="sectionTitleBg" x="60" y="240" width="420" height="44" rx="18"/>
    <text class="sectionTitle" x="82" y="270">SECTION 1: Income → Repayment</text>

    <text class="micro" x="82" y="302">Shows: repayment as a share of monthly gross income.</text>

    <text class="label" x="82" y="330">Repayment ratio</text>
    <text class="big" x="82" y="370">{{s1_ratio_pct}}%</text>
    <text class="muted" x="82" y="400">Repayment: {{s1_repayment_monthly}} / month</text>

    <!-- Zone pill (kept left) -->
    <rect x="82" y="430" width="220" height="34" rx="10" fill="{{s1_zone_color}}"/>
    <text class="zone" x="96" y="454">{{s1_zone_label}}</text>

    <!-- Gauge moved right so needle never collides with pill -->
    <path d="M210 520 A120 120 0 0 1 430 520" fill="none" stroke="#E3EAF3" stroke-width="22"/>
    <path d="M210 520 A120 120 0 0 1 430 520" fill="none" stroke="{{s1_zone_color}}" stroke-width="22" stroke-linecap="round" opacity="0.9"/>

    <circle cx="320" cy="520" r="9" fill="#0E2A47"/>
    <g transform="translate(320 520) rotate({{s1_needle_angle}})">
      <line x1="0" y1="0" x2="0" y2="-88" stroke="#0E2A47" stroke-width="6" stroke-linecap="round"/>
    </g>
  </g>

  <!-- SECTION 2 -->
  <g id="section2">
    <rect class="card" x="544" y="240" width="420" height="310" rx="18"/>
    <rect class="sectionTitleBg" x="544" y="240" width="420" height="44" rx="18"/>
    <text class="sectionTitle" x="566" y="270">SECTION 2: Loan size → Income</text>

    <text class="micro" x="566" y="302">Shows: loan amount compared with annual gross income.</text>

    <text class="label" x="566" y="330">Exposure</text>
    <text class="big" x="566" y="370">{{s2_exposure_pct}}%</text>
    <text class="muted" x="566" y="400">Loan: {{s2_loan_amount}}</text>

    <rect x="892" y="320" width="26" height="190" rx="13" fill="#E3EAF3"/>
    <rect x="892" y="{{s2_fill_y}}" width="26" height="{{s2_fill_height}}" rx="13" fill="{{s2_zone_color}}"/>

    <rect x="566" y="430" width="220" height="34" rx="10" fill="{{s2_zone_color}}"/>
    <text class="zone" x="580" y="454">{{s2_zone_label}}</text>
  </g>

  <!-- SECTION 3 -->
  <g id="section3">
    <rect class="card" x="60" y="580" width="420" height="310" rx="18"/>
    <rect class="sectionTitleBg" x="60" y="580" width="420" height="44" rx="18"/>
    <text class="sectionTitle" x="82" y="610">SECTION 3: Car price → Income</text>

    <text class="micro" x="82" y="642">Shows: purchase price compared with annual gross income.</text>

    <text class="label" x="82" y="670">Car price ratio</text>
    <text class="big" x="82" y="710">{{s3_car_price_pct}}%</text>

    <rect x="82" y="750" width="356" height="20" rx="10" fill="#E3EAF3"/>
    <rect x="82" y="750" width="{{s3_band_fill_w}}" height="20" rx="10" fill="{{s3_zone_color}}"/>
    <line x1="{{s3_marker_x}}" y1="740" x2="{{s3_marker_x}}" y2="778" stroke="#0E2A47" stroke-width="3"/>

    <rect x="82" y="800" width="220" height="34" rx="10" fill="{{s3_zone_color}}"/>
    <text class="zone" x="96" y="824">{{s3_zone_label}}</text>
  </g>

  <!-- SECTION 4 -->
  <g id="section4">
    <rect class="card" x="544" y="580" width="420" height="310" rx="18"/>
    <rect class="sectionTitleBg" x="544" y="580" width="420" height="44" rx="18"/>
    <text class="sectionTitle" x="566" y="610">SECTION 4: Term vs car life</text>

    <text class="micro" x="566" y="642">Shows: whether the term ends before reliability declines.</text>

    <text class="muted" x="566" y="675">Age now: {{s4_age_now}} yrs</text>
    <text class="muted" x="566" y="700">Age at end: {{s4_age_end}} yrs</text>
    <text class="muted" x="566" y="725">Term: {{s4_term_years}} yrs</text>

    <rect x="566" y="752" width="356" height="16" rx="8" fill="#E3EAF3"/>
    <rect x="566" y="752" width="{{s4_timeline_end_x}}" height="16" rx="8" fill="{{s4_zone_color}}"/>

    <rect x="566" y="800" width="220" height="34" rx="10" fill="{{s4_zone_color}}"/>
    <text class="zone" x="580" y="824">{{s4_zone_label}}</text>
  </g>

  <!-- SECTION 5 -->
  <g id="section5">
    <rect class="card" x="60" y="920" width="420" height="260" rx="18"/>
    <rect class="sectionTitleBg" x="60" y="920" width="420" height="44" rx="18"/>
    <text class="sectionTitle" x="82" y="950">SECTION 5: Rate risk zones</text>

    <text class="micro" x="82" y="982">Shows: interest-rate risk zone (proxy for lender pricing).</text>

    <text class="label" x="82" y="1010">APR</text>
    <text class="big" x="82" y="1050">{{s5_apr}}%</text>

    <rect x="82" y="1090" width="220" height="34" rx="10" fill="{{s5_zone_color}}"/>
    <text class="zone" x="96" y="1114">{{s5_zone_label}}</text>
  </g>

  <!-- SECTION 6 -->
  <g id="section6">
    <rect class="card" x="544" y="920" width="420" height="260" rx="18"/>
    <rect class="sectionTitleBg" x="544" y="920" width="420" height="44" rx="18"/>
    <text class="sectionTitle" x="566" y="950">SECTION 6: Emergency buffer</text>

    <text class="micro" x="566" y="982">Shows: savings months after essential costs (estimated).</text>

    <text class="muted" x="566" y="1010">Essentials (assumed): {{s6_essentials_monthly}} / month</text>
    <text class="big" x="566" y="1050">{{s6_buffer_months}} months</text>

    <rect x="892" y="1000" width="36" height="130" rx="12" fill="#E3EAF3"/>
    <rect x="892" y="{{s6_fill_y}}" width="36" height="{{s6_fill_h}}" rx="12" fill="{{s6_zone_color}}"/>

    <rect x="566" y="1090" width="220" height="34" rx="10" fill="{{s6_zone_color}}"/>
    <text class="zone" x="580" y="1114">{{s6_zone_label}}</text>
  </g>

  <!-- SECTION 7 -->
  <g id="section7">
    <rect class="card" x="60" y="1210" width="904" height="250" rx="18"/>
    <rect class="sectionTitleBg" x="60" y="1210" width="904" height="44" rx="18"/>
    <text class="sectionTitle" x="82" y="1240">SECTION 7: All-in car cost rule</text>

    <text class="micro" x="82" y="1272">Shows: (repayment + running cost estimate) as share of monthly income.</text>

    <text class="label" x="82" y="1298">All-in cost ratio</text>
    <text class="big" x="82" y="1338">{{s7_allin_pct}}%</text>
    <text class="muted" x="82" y="1368">All-in: {{s7_allin_monthly}} / month</text>
    <text class="muted" x="82" y="1392">Running cost assumption: {{s7_running_cost_assumed}} / month</text>

    <path d="M520 1430 A160 160 0 0 1 840 1430" fill="none" stroke="#E3EAF3" stroke-width="24"/>
    <path d="M520 1430 A160 160 0 0 1 840 1430" fill="none" stroke="{{s7_zone_color}}" stroke-width="24" stroke-linecap="round" opacity="0.9"/>

    <circle cx="680" cy="1430" r="10" fill="#0E2A47"/>
    <g transform="translate(680 1430) rotate({{s7_needle_angle}})">
      <line x1="0" y1="0" x2="0" y2="-132" stroke="#0E2A47" stroke-width="7" stroke-linecap="round"/>
    </g>

    <rect x="82" y="1410" width="220" height="34" rx="10" fill="{{s7_zone_color}}"/>
    <text class="zone" x="96" y="1434">{{s7_zone_label}}</text>
  </g>

  <text class="muted" x="60" y="1505">{{footer_note}}</text>
</svg>
"""


# ============================================================
# Streamlit app
# ============================================================
st.set_page_config(page_title="Smart Car Loan Framework (AU)", layout="wide")

st.title("Smart Car Loan Framework (AU) — Live Infographic")

# ------------------------------------------------------------
# Overview window: Intro + governing equations + how to read
# ------------------------------------------------------------
with st.container():
    st.markdown("### Overview")
    st.markdown(
        """
This app turns a small set of inputs into a **live affordability and resilience check** for a car purchase in Australia.

It does **not** predict bank approval and it is **not financial advice**. Instead, it applies conservative bank-style ratios to show where risk tends to rise:
- repayment pressure,
- loan size vs income,
- car price vs income,
- term vs likely reliable life,
- interest-rate risk zone,
- emergency buffer, and
- all-in ownership load.

The infographic updates immediately as you change inputs.
        """.strip()
    )

    with st.expander("Governing equations (with explanations)", expanded=False):
        st.markdown("#### A) Rates and time")
        c1, c2 = st.columns(2)
        with c1:
            st.latex(r"r = \frac{\mathrm{APR}}{12}")
            st.caption("Monthly interest rate.")
        with c2:
            st.latex(r"n = 12T")
            st.caption("Number of monthly payments (T in years).")

        st.divider()

        st.markdown("#### B) Balloon (optional)")
        st.latex(r"\mathrm{PV}(B) = \frac{B}{(1+r)^n}")
        st.latex(r"P_{\mathrm{eff}} = P - \mathrm{PV}(B)")
        st.caption("If there is no balloon, set \(B=0\), so \(P_{\\mathrm{eff}}=P\).")

        st.divider()

        st.markdown("#### C) Monthly repayment (amortising loan)")
        st.latex(r"M = P_{\mathrm{eff}} \cdot \frac{r(1+r)^n}{(1+r)^n - 1}")
        st.markdown("**Zero-rate special case**")
        st.latex(r"M = \frac{P - B}{n}\quad\text{when }r=0")
        st.caption("This monthly repayment \(M\) drives Section 1 and the all-in rule.")

        st.divider()

        st.markdown("#### D) Ratios used in the infographic")
        c1, c2 = st.columns(2)
        with c1:
            st.latex(r"\text{Repayment ratio} = \frac{M}{I_m}")
            st.caption("Section 1: repayment pressure vs monthly gross income.")
            st.latex(r"\text{Loan exposure} = \frac{P}{I_y}")
            st.caption("Section 2: loan size vs annual gross income.")
        with c2:
            st.latex(r"\text{Car price ratio} = \frac{C}{I_y}")
            st.caption("Section 3: purchase price vs annual gross income.")
            st.latex(r"\text{All-in ratio} = \frac{M + R_m}{I_m}")
            st.caption("Section 7: repayment plus running costs vs monthly gross income.")

        st.caption(
            r"Where \(I_m\) is monthly gross income, \(I_y\) is annual gross income, "
            r"\(P\) is loan amount, \(C\) is car price, and \(R_m\) is monthly running-cost estimate."
        )

        st.divider()

        st.markdown("#### E) Buffer and lifetime cost")
        st.latex(r"\text{Buffer months} = \frac{S}{E_m}")
        st.caption("Section 6: savings divided by estimated essential monthly costs.")
        st.latex(r"\text{Total paid} = 12TM + B")
        st.latex(r"\text{Total interest} = \text{Total paid} - P")
        st.caption("Key numbers: total interest is lifetime cost of borrowing.")

    st.caption(
        "Tip: Use the defaults first. Only open Advanced assumptions if you want to adjust how conservative the buffer/running-cost estimates are."
    )

st.divider()
# ------------------------------------------------------------
# Main two-column layout
# ------------------------------------------------------------
left, right = st.columns([1, 1.6])

# Defaults via session_state (stable, explicit)
if "essentials_floor_ratio" not in st.session_state:
    st.session_state.essentials_floor_ratio = 0.45
if "older_car_age_cutoff" not in st.session_state:
    st.session_state.older_car_age_cutoff = 8
if "running_cost_ratio_newer" not in st.session_state:
    st.session_state.running_cost_ratio_newer = 0.06
if "running_cost_ratio_older" not in st.session_state:
    st.session_state.running_cost_ratio_older = 0.08

with left:
    st.subheader("Step 1 — Money snapshot")

    st.caption(
        "Enter only what you know. The app uses simple, conservative assumptions where full budgeting detail would be painful to gather."
    )

    income_freq = st.selectbox("Gross income frequency", ["monthly", "fortnightly", "weekly"], index=0)
    income_amount = st.number_input("Gross income", min_value=0.0, value=6000.0, step=100.0)
    gross_income_monthly = to_monthly(income_amount, income_freq)

    st.caption(
        f"Repayment guideline (10–15% of gross): {fmt_money(gross_income_monthly*0.10)}–{fmt_money(gross_income_monthly*0.15)} / month"
    )
    st.caption(f"All-in guideline (≤20% of gross): {fmt_money(gross_income_monthly*0.20)} / month")

    # Housing cost now weekly (requested)
    housing_weekly = st.number_input("Housing cost (rent/mortgage) — weekly", min_value=0.0, value=500.0, step=10.0)
    housing_monthly = to_monthly(housing_weekly, "weekly")
    st.caption(f"Monthly equivalent (auto): {fmt_money(housing_monthly)} / month")

    if gross_income_monthly > 0:
        st.caption(f"Housing share: {fmt_pct_ratio(housing_monthly / gross_income_monthly, 1)}% of gross income")

    existing_debt = st.number_input(
        "Existing debt repayments — monthly (non-car)", min_value=0.0, value=0.0, step=50.0
    )
    headroom_low = max(0.0, gross_income_monthly * 0.10 - existing_debt)
    headroom_high = max(0.0, gross_income_monthly * 0.15 - existing_debt)
    st.caption(f"Repayment headroom vs 10–15% band: {fmt_money(headroom_low)}–{fmt_money(headroom_high)} / month")

    savings_available = st.number_input("Savings available (liquid)", min_value=0.0, value=5000.0, step=250.0)
    st.caption("Used for the emergency buffer calculation (Section 6).")

    st.subheader("Step 2 — Car + loan basics")

    car_price = st.number_input("Car price (drive-away)", min_value=0.0, value=25000.0, step=500.0)

    annual_income = gross_income_monthly * 12
    if annual_income > 0:
        st.caption(
            f"Car price guideline (35–50% annual income): {fmt_money(annual_income*0.35)}–{fmt_money(annual_income*0.50)}"
        )
        st.caption(f"Financial stress marker (70%): {fmt_money(annual_income*0.70)}")

    deposit = st.number_input("Deposit / trade-in", min_value=0.0, value=3000.0, step=250.0)
    deposit = min(deposit, car_price)
    loan_amount = max(0.0, car_price - deposit)
    st.caption(f"Estimated loan amount (price − deposit): {fmt_money(loan_amount)}")

    current_year = datetime.now().year
    car_year = st.number_input(
        "Car build year", min_value=1990, max_value=current_year + 1, value=min(2018, current_year), step=1
    )
    car_age_now = max(0.0, current_year - int(car_year))
    st.caption("Used to suggest a term that ends before likely reliability declines.")

    rate_mode = st.radio("Interest rate", ["Assumed (default)", "Custom"], horizontal=True)
    apr_assumed = 9.0
    if rate_mode.startswith("Custom"):
        apr = st.number_input("APR (%)", min_value=0.0, max_value=40.0, value=9.0, step=0.25)
        st.caption("Use the APR from your quote. Higher APR increases repayment and total interest.")
    else:
        apr = apr_assumed
        st.caption(f"Using assumed APR: {apr_assumed:.2f}% (switch to Custom if you have a quote)")

    term_mode = st.radio("Term", ["Auto (recommended)", "Custom"], horizontal=True)
    term_auto = term_years_auto(car_age_now)
    if term_mode.startswith("Custom"):
        term_years = st.number_input("Term (years)", min_value=1.0, max_value=7.0, value=float(term_auto), step=0.5)
    else:
        term_years = term_auto
        st.caption(f"Suggested term from car age: {term_auto:.1f} years")

    balloon_mode = st.radio("Balloon (optional)", ["None", "Custom"], horizontal=True)
    if balloon_mode.startswith("Custom"):
        balloon_amount = st.number_input(
            "Balloon amount ($)", min_value=0.0, max_value=float(loan_amount), value=0.0, step=250.0
        )
        st.caption("A balloon reduces monthly repayments but can increase residual risk at the end.")
    else:
        balloon_amount = 0.0

    with st.expander("Advanced assumptions (optional)", expanded=False):
        st.markdown(
            """
These settings exist so you **don’t** need a full budget. They control how conservative the app is when estimating:
- “essential monthly costs” for the buffer, and
- running/ownership costs for the all-in rule.
            """.strip()
        )

        st.session_state.essentials_floor_ratio = st.slider(
            "Essentials floor (share of gross income)",
            min_value=0.30,
            max_value=0.65,
            value=float(st.session_state.essentials_floor_ratio),
            step=0.01,
            help="Lower = more optimistic buffer. Higher = more conservative buffer estimate.",
        )
        st.caption(
            "If your reported housing+debt look too low, this floor prevents an unrealistic buffer result."
        )

        st.session_state.older_car_age_cutoff = st.slider(
            "Older-car cutoff (years)",
            min_value=6,
            max_value=12,
            value=int(st.session_state.older_car_age_cutoff),
            step=1,
            help="If the car age is above this cutoff, the app uses the ‘older car’ running-cost ratio.",
        )
        st.caption("This switches the running-cost assumption upward for older vehicles.")

        st.session_state.running_cost_ratio_newer = st.slider(
            "Running cost ratio (newer car, per year as % of price)",
            0.03,
            0.10,
            float(st.session_state.running_cost_ratio_newer),
            0.005,
            help="Annual running cost estimate for newer cars (maintenance/tyres/minor repairs proxy).",
        )
        st.caption("Example: 0.06 means ~6% of purchase price per year, converted to monthly.")

        st.session_state.running_cost_ratio_older = st.slider(
            "Running cost ratio (older car, per year as % of price)",
            0.04,
            0.12,
            float(st.session_state.running_cost_ratio_older),
            0.005,
            help="Annual running cost estimate for older cars (more conservative).",
        )
        st.caption("Higher values increase the all-in cost ratio (Section 7).")

# ------------------------------------------------------------
# Calculations
# ------------------------------------------------------------
repayment = amortised_repayment_monthly(loan_amount, apr, term_years, balloon_amount)
total_paid, total_interest = totals_from_repayment(loan_amount, repayment, term_years, balloon_amount)

repayment_ratio = repayment / gross_income_monthly if gross_income_monthly > 0 else 0.0
loan_to_income = loan_amount / annual_income if annual_income > 0 else 0.0
car_price_ratio = car_price / annual_income if annual_income > 0 else 0.0
car_age_end = car_age_now + term_years

# Essentials estimate (transparent + minimal)
essentials_est = max(
    housing_monthly + existing_debt + 0.25 * gross_income_monthly,  # light baseline
    st.session_state.essentials_floor_ratio * gross_income_monthly,  # floor to avoid unrealistic buffers
)
buffer_months = (savings_available / essentials_est) if essentials_est > 0 else 0.0

# Running cost estimate
running_ratio = (
    st.session_state.running_cost_ratio_newer
    if car_age_now < st.session_state.older_car_age_cutoff
    else st.session_state.running_cost_ratio_older
)
running_cost_monthly = (running_ratio * car_price) / 12 if car_price > 0 else 0.0

all_in_monthly = repayment + running_cost_monthly
all_in_ratio = all_in_monthly / gross_income_monthly if gross_income_monthly > 0 else 0.0

# Zones
s1_label, s1_col = zone_s1(repayment_ratio)
s2_label, s2_col = zone_s2(loan_to_income)
s3_label, s3_col = zone_s3(car_price_ratio)
s4_label, s4_col = zone_s4(car_age_end)
s5_label, s5_col = zone_s5(apr)
s6_label, s6_col = zone_s6(buffer_months)
s7_label, s7_col = zone_s7(all_in_ratio)


def severity(col: str) -> int:
    if col == COL_GREEN:
        return 0
    if col == COL_AMBER:
        return 1
    return 2


sections = [
    ("Repayment", severity(s1_col), repayment_ratio * 100),
    ("Exposure", severity(s2_col), loan_to_income * 100),
    ("Car price", severity(s3_col), car_price_ratio * 100),
    ("Term", severity(s4_col), car_age_end),
    ("Buffer", severity(s6_col), buffer_months),
    ("All-in", severity(s7_col), all_in_ratio * 100),
]
score = sum(s for _, s, _ in sections)
driver = sorted(sections, key=lambda t: (t[1], t[2]), reverse=True)[0][0]

if score <= 2:
    headline_resilience = "High"
    headline_color = COL_GREEN
elif score <= 6:
    headline_resilience = "Medium"
    headline_color = COL_AMBER
else:
    headline_resilience = "Low"
    headline_color = COL_RED

# Geometry
s1_angle = needle_angle_from_pct(repayment_ratio * 100, pct_max=25.0)
s7_angle = needle_angle_from_pct(all_in_ratio * 100, pct_max=30.0)
s2_fill_y, s2_fill_h = thermometer_fill(loan_to_income * 100)
s3_marker_x, s3_fill_w = band_marker_x(car_price_ratio * 100)
s4_timeline_w = timeline_fill(car_age_end)
s6_fill_y, s6_fill_h = jar_fill(buffer_months)

footer_note = (
    "Guidelines only. Assumptions shown. "
    f"Payment {fmt_money(repayment)}/mo • Interest {fmt_money(total_interest)} • Total {fmt_money(total_paid)}."
)

token_map = {
    "headline_color": headline_color,
    "headline_resilience": headline_resilience,
    "headline_driver": driver,
    "s1_ratio_pct": f"{repayment_ratio * 100:.1f}",
    "s1_repayment_monthly": fmt_money(repayment),
    "s1_zone_label": s1_label,
    "s1_zone_color": s1_col,
    "s1_needle_angle": f"{s1_angle:.2f}",
    "s2_exposure_pct": f"{loan_to_income * 100:.1f}",
    "s2_loan_amount": fmt_money(loan_amount),
    "s2_zone_label": s2_label,
    "s2_zone_color": s2_col,
    "s2_fill_y": f"{s2_fill_y:.2f}",
    "s2_fill_height": f"{s2_fill_h:.2f}",
    "s3_car_price_pct": f"{car_price_ratio * 100:.1f}",
    "s3_zone_label": s3_label,
    "s3_zone_color": s3_col,
    "s3_marker_x": f"{s3_marker_x:.2f}",
    "s3_band_fill_w": f"{s3_fill_w:.2f}",
    "s4_age_now": f"{car_age_now:.0f}",
    "s4_age_end": f"{car_age_end:.0f}",
    "s4_term_years": f"{term_years:.1f}",
    "s4_zone_label": s4_label,
    "s4_zone_color": s4_col,
    "s4_timeline_end_x": f"{s4_timeline_w:.2f}",
    "s5_apr": f"{apr:.2f}",
    "s5_zone_label": s5_label,
    "s5_zone_color": s5_col,
    "s6_buffer_months": f"{buffer_months:.1f}",
    "s6_essentials_monthly": fmt_money(essentials_est),
    "s6_zone_label": s6_label,
    "s6_zone_color": s6_col,
    "s6_fill_y": f"{s6_fill_y:.2f}",
    "s6_fill_h": f"{s6_fill_h:.2f}",
    "s7_allin_pct": f"{all_in_ratio * 100:.1f}",
    "s7_allin_monthly": fmt_money(all_in_monthly),
    "s7_running_cost_assumed": fmt_money(running_cost_monthly),
    "s7_zone_label": s7_label,
    "s7_zone_color": s7_col,
    "s7_needle_angle": f"{s7_angle:.2f}",
    "footer_note": footer_note,
}

svg = replace_tokens(SVG_TEMPLATE, token_map)

# ------------------------------------------------------------
# Render infographic (right column)
# ------------------------------------------------------------
with right:
    st.subheader("Live infographic")
    components.html(
        f'<div style="width:100%; overflow:hidden;">{svg}</div>',
        height=1600,
    )

st.divider()

# ------------------------------------------------------------
# Key numbers window below infographic (with explanations)
# ------------------------------------------------------------
st.markdown("### Key numbers (what they mean)")

k1, k2, k3 = st.columns(3)

with k1:
    st.metric("Loan amount", fmt_money(loan_amount))
    st.caption("Estimated borrowed amount: car price minus deposit/trade-in.")

    st.metric("Monthly repayment", fmt_money(repayment))
    st.caption("Estimated instalment using the amortisation equation and your APR/term (balloon-adjusted if used).")

with k2:
    st.metric("Total interest (estimate)", fmt_money(total_interest))
    st.caption("Total paid minus the original loan amount. Useful for comparing offers and terms.")

    st.metric("Total paid (estimate)", fmt_money(total_paid))
    st.caption("Repayments across the full term plus any balloon amount.")

with k3:
    st.metric("Running costs (assumed / month)", fmt_money(running_cost_monthly))
    st.caption("A simple ownership-cost proxy (maintenance/repairs/tyres). Controlled in Advanced assumptions.")

    st.metric("All-in cost (monthly)", fmt_money(all_in_monthly))
    st.caption("Repayment + running-cost estimate. Used in Section 7 to cap total car load (≤20% guideline).")

st.metric("Emergency buffer (months)", f"{buffer_months:.2f}")
st.caption(
    "Savings divided by estimated essential monthly costs. Higher is more resilient (3–6 months is the guideline range)."
)
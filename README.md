# Advanced Car Loan Framework (AU) — Live Infographic

Interactive **Streamlit** app that visualises evidence-based car-loan affordability ratios commonly used by Australian lenders and regulators as risk guidelines.

It focuses on *resilience* (ability to carry the loan safely), not “approval prediction”.

## What it does
- Converts minimal inputs (income, housing, savings, car price, deposit, APR, term) into live ratios
- Shows 7 sections in an infographic:
  1) Repayment ratio (monthly repayment vs monthly gross income)  
  2) Loan exposure (loan vs annual income)  
  3) Car price ratio (car price vs annual income)  
  4) Term vs car life alignment (age at end of term)  
  5) Interest-rate risk zone  
  6) Emergency buffer (months of essentials covered by savings)  
  7) All-in cost ratio (repayment + running cost estimate vs income)

## Inputs
The app is designed to keep inputs minimal:
- Gross income (weekly/fortnightly/monthly)
- Housing cost (weekly)
- Existing non-car debt repayments (monthly)
- Savings available (liquid)
- Car price (drive-away) and deposit / trade-in
- Car build year
- APR (assumed or custom)
- Term (auto recommended or custom)
- Optional balloon
- Optional advanced assumptions (buffer floor and running-cost ratios)

## Disclaimer
This tool provides **guidelines only** and is **not financial advice**.
It does not guarantee lender approval and uses simplified assumptions for budgeting/running costs.

## Run locally (Windows / VS Code)
1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate

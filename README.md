# 🔍 Fairlens

> *A second look before the algorithm decides.*

A web app that audits machine-learning training datasets for **demographic bias** —
**before** a model is trained, catching problems at the data source rather than after deployment.

---

## 🌐 Live Demo

👉 https://fairlens-live.onrender.com

> ⚠️ Hosted on Render free tier — the first request may take ~30–60s to wake up.

---

## 🎯 What it does

Upload a CSV (or try a sample) and Fairlens runs **four checks**, then combines them into a single **Bias Score (0–10)**:

| Module | What it checks | Method |
|---|---|---|
| **Representation** | Is any demographic group over/under-represented? | group-share spread |
| **Proxy detector** | Does a normal column secretly encode a protected attribute? | Cramér's V / correlation ratio |
| **Outcome gap** | Do approval/selection rates differ across groups? | EEOC 80% rule |
| **Data quality** | How much data is missing per column? | missingness % |

```
penalty     = 0.25·representation + 0.30·proxy + 0.35·outcome_gap + 0.10·quality
Bias score  = 10 × (1 − penalty)
```

### Bias Score — range & meaning

The score ranges from **0 (very biased)** to **10 (fair)**:

| Score | Label | Meaning |
|-------|-------|---------|
| **8 – 10** | 🟢 Mostly fair | Minimal bias — safe to proceed with care |
| **6 – 8** | 🟡 Needs attention | Moderate issues — review before training |
| **4 – 6** | 🟠 High risk | Significant bias — fix before using |
| **0 – 4** | 🔴 Critical bias | Severe bias — must be fixed first |

Each of the four checks is rated *ok / warning / critical*, weighted by the values above, and combined into this single score.

### Which columns it detects

Columns are detected automatically by matching keywords in their names:

| Type | Detected when the column name contains… |
|------|------------------------------------------|
| **Protected attributes** | `gender` / `sex`, `religion`, `caste`, `race` / `ethnicity`, `age`, `region` / `area` / `location` |
| **Proxy suspects** | `pincode` / `zip`, `surname` / `last_name`, `address`, `college` / `school` / `board`, `hobbies`, `name` |
| **Outcome** | `approved`, `selected`, `admitted`, `hired`, `outcome`, `result`, `label`, `target`, `decision` |

So the four bias checks work best on datasets that include at least one of these protected columns (and, for the outcome-gap check, an outcome column).

---

## 🖥 Interface

Intentionally **humanistic** — reads like a thoughtful auditor, not a dashboard.

- Warm cream + terracotta palette
- Fraunces serif headings, Inter body, Caveat handwritten accents
- Plain-language insights instead of raw metrics

---

## 🛠 Tech stack

| Layer | Tools |
|---|---|
| Web framework | Flask |
| Data & statistics | pandas · NumPy |
| Frontend | Vanilla HTML5 · CSS3 · JavaScript (no framework, no build step) |
| Server | Gunicorn |

**Statistics used:** Chi-square test · Cramér's V (categorical association) · Correlation ratio η (numeric ↔ categorical) · EEOC 80% rule (disparate impact).

---

## 📁 Project structure

```
fairlens/
├── index.html            Frontend
├── styles.css
├── script.js
└── backend/
    ├── app.py            Flask API (serve frontend + audit endpoints)
    ├── audit_engine.py   Bias-detection logic (4 checks + score)
    ├── generate_samples.py
    ├── requirements.txt
    └── sample_data/      loan / hiring / admissions CSVs
```

---

## ▶️ Run locally

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py            # open the printed http://localhost:<port>
```

---

## 📊 Sample datasets

Three synthetic datasets with known injected bias patterns:

| Dataset | Rows | Bias |
|---|---|---|
| `loan_data.csv` | 1,000 | Gender imbalance, pincode as a proxy, gender outcome gap |
| `hiring_data.csv` | 820 | Gender bias with hobby proxies |
| `admissions_data.csv` | 1,500 | Mostly fair (passes the 80% rule) |

---

## ⚠️ Limitations

This is a focused prototype, not a production-grade tool. Known limitations:

- **Name-based detection** — columns are found by keyword in their *names* (`gender`, `pincode`, `approved`); unusual names (e.g. `g1`) are missed.
- **Demographic bias only** — covers gender, religion, caste, race, age, region; sampling/measurement/label bias are out of scope.
- **Numeric attributes & small data** — numeric columns like `age` aren't bucketed into ranges (each value becomes its own group), and on very few rows the Cramér's V correlations can be coincidental. Works best on categorical attributes with hundreds+ rows.
- **Simplified scoring** — uses only the first detected protected column, rates each check coarsely (ok / warning / critical) rather than continuously, and gives rule-based (templated) fix suggestions.
- **Outcome gap needs a label** — the 80% rule needs a labelled outcome column; the other three checks work without one.

## ☁️ Deploy (Render)

- **Build command:** `pip install -r backend/requirements.txt`
- **Start command:** `gunicorn --chdir backend app:app`

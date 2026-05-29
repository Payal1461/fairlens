"""
Fairlens — Real Bias Audit Engine
Computes:
  1. Demographic representation (chi-square + percentages)
  2. Proxy variable detection (Cramér's V for cat/cat, eta-squared for num/cat)
  3. Outcome gap (80% rule / disparate impact)
  4. Data quality (missingness)
  5. Overall bias score (weighted)
"""
from __future__ import annotations
import io
import math
import re
import pandas as pd
import numpy as np
from typing import Any

# ---- Heuristic column detection ----
PROTECTED_HINTS = {
    "gender": ["gender", "sex"],
    "religion": ["religion"],
    "caste": ["caste"],
    "race": ["race", "ethnicity"],
    "age": ["age"],
    "region": ["region", "area", "location"],
}
PROXY_SUSPECTS = ["pincode", "zip", "surname", "lastname", "last_name", "address",
                  "college", "school", "board", "hobbies", "name"]
OUTCOME_HINTS = ["approved", "selected", "admitted", "hired", "outcome", "result", "label", "target", "decision"]


def detect_columns(df: pd.DataFrame) -> dict:
    """Best-effort detection of protected, proxy, and outcome columns."""
    cols = [c.lower() for c in df.columns]
    actual = {c.lower(): c for c in df.columns}

    protected = []
    for lc in cols:
        for hints in PROTECTED_HINTS.values():
            if any(h in lc for h in hints):
                protected.append(actual[lc])
                break

    proxies = [actual[lc] for lc in cols if any(s in lc for s in PROXY_SUSPECTS) and actual[lc] not in protected]

    outcome = None
    for lc in cols:
        if any(h in lc for h in OUTCOME_HINTS):
            outcome = actual[lc]
            break

    return {"protected": protected, "proxy_suspects": proxies, "outcome": outcome}


# ---- Statistical helpers ----
def cramers_v(a: pd.Series, b: pd.Series) -> float:
    """Cramér's V correlation between two categorical Series."""
    confusion = pd.crosstab(a, b)
    if confusion.size == 0 or confusion.shape[0] < 2 or confusion.shape[1] < 2:
        return 0.0
    # chi-square computed directly with numpy (no scipy dependency)
    obs = confusion.values.astype(float)
    row_sums = obs.sum(axis=1, keepdims=True)
    col_sums = obs.sum(axis=0, keepdims=True)
    n = obs.sum()
    if n == 0:
        return 0.0
    expected = row_sums @ col_sums / n
    chi2 = float(np.nansum((obs - expected) ** 2 / expected))
    phi2 = chi2 / n
    r, k = confusion.shape
    denom = min(k - 1, r - 1)
    return float(math.sqrt(phi2 / denom)) if denom > 0 else 0.0


def correlation_ratio(categories: pd.Series, values: pd.Series) -> float:
    """Eta — correlation ratio for categorical-numerical."""
    df = pd.DataFrame({"c": categories, "v": values}).dropna()
    if df.empty:
        return 0.0
    cats = df["c"].unique()
    if len(cats) < 2:
        return 0.0
    overall = df["v"].mean()
    num = sum(len(df[df.c == c]) * (df[df.c == c]["v"].mean() - overall) ** 2 for c in cats)
    den = ((df["v"] - overall) ** 2).sum()
    if den == 0:
        return 0.0
    return float(math.sqrt(num / den))


def is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s)


# ===========================================================
# MODULE 1 — Representation
# ===========================================================
def analyze_representation(df: pd.DataFrame, protected_col: str | None) -> dict:
    if not protected_col:
        return {"available": False, "summary": "No protected attribute column detected.", "bars": []}

    counts = df[protected_col].value_counts(dropna=False)
    total = counts.sum()
    bars = []
    for label, count in counts.items():
        pct = round(100 * count / total, 1)
        cls = "male" if str(label).lower().startswith("m") else ("female" if str(label).lower().startswith("f") else "other")
        bars.append({"label": str(label), "value": pct, "count": int(count), "class": cls})

    # representation severity
    min_pct = min(b["value"] for b in bars)
    if min_pct < 15:
        severity = "crit"
        title = "Some voices are barely heard"
        summary = (f"Your dataset is heavily skewed — the smallest group ({bars[-1]['label']}) "
                   f"is only {min_pct}% of the data. A model trained on this will know one group well and others poorly.")
    elif min_pct < 30:
        severity = "warn"
        title = "Some voices are missing"
        summary = (f"Distribution is uneven — {bars[0]['label']} is {bars[0]['value']}%, "
                   f"while {bars[-1]['label']} is only {bars[-1]['value']}%. The model will learn one group better than the other.")
    else:
        severity = "ok"
        title = "Most groups are present"
        summary = f"Distribution across {protected_col} looks reasonably balanced."

    fix = ("→ Try oversampling underrepresented groups (SMOTE), or collect more data before training."
           if severity != "ok" else "→ Balance is fine. No action needed.")

    return {
        "available": True,
        "column": protected_col,
        "title": title,
        "summary": summary,
        "severity": severity,
        "bars": bars,
        "fix": fix,
    }


# ===========================================================
# MODULE 2 — Proxy detection
# ===========================================================
def analyze_proxies(df: pd.DataFrame, protected_cols: list, proxy_candidates: list) -> dict:
    items = []
    for proxy in proxy_candidates:
        for target in protected_cols:
            if proxy == target:
                continue
            try:
                # categorical-categorical → Cramér's V
                if not is_numeric(df[proxy]) and not is_numeric(df[target]):
                    score = cramers_v(df[proxy].astype(str), df[target].astype(str))
                elif is_numeric(df[proxy]) and not is_numeric(df[target]):
                    score = correlation_ratio(df[target].astype(str), df[proxy])
                elif not is_numeric(df[proxy]) and is_numeric(df[target]):
                    score = correlation_ratio(df[proxy].astype(str), df[target])
                else:
                    score = abs(df[proxy].corr(df[target]))
                if math.isnan(score):
                    score = 0.0
            except Exception:
                score = 0.0

            if score >= 0.3:
                severity = "crit" if score >= 0.6 else "warn"
                items.append({
                    "col": proxy,
                    "target": target,
                    "score": round(score, 2),
                    "score_label": f"r = {round(score, 2)}",
                    "severity": severity
                })

    items.sort(key=lambda x: -x["score"])
    items = items[:5]

    if not items:
        return {
            "available": True,
            "title": "No obvious proxies",
            "summary": "We didn't find columns that secretly carry protected information. Nice.",
            "severity": "ok",
            "items": [],
            "fix": "→ Nothing to fix here."
        }

    if any(i["severity"] == "crit" for i in items):
        severity = "crit"
        title = "A column is doing something it shouldn't"
        top = items[0]
        summary = (f"<strong>{top['col']}</strong> shows a {top['score']} correlation with "
                   f"<strong>{top['target']}</strong>. Even if you drop the protected column, the model will infer it from this proxy.")
    else:
        severity = "warn"
        title = "Some columns whisper too loudly"
        top = items[0]
        summary = (f"<strong>{top['col']}</strong> carries some signal about <strong>{top['target']}</strong> "
                   f"({top['score']} correlation). Worth a closer look.")

    fix = "→ Drop these columns, or transform them (e.g., bucket pincodes into broader regions)."

    return {
        "available": True,
        "title": title,
        "summary": summary,
        "severity": severity,
        "items": items,
        "fix": fix
    }


# ===========================================================
# MODULE 3 — Outcome gap (80% rule)
# ===========================================================
def analyze_gap(df: pd.DataFrame, protected_col: str | None, outcome_col: str | None) -> dict:
    if not protected_col or not outcome_col:
        return {"available": False, "summary": "Outcome column not detected — cannot measure gap."}

    # find the "positive" class (Yes / 1 / True)
    series = df[outcome_col].astype(str).str.lower()
    pos_candidates = ["yes", "y", "true", "1", "approved", "selected", "admitted", "hired", "positive"]
    pos = next((p for p in pos_candidates if p in series.unique()), None)
    if not pos:
        pos = series.mode().iloc[0]

    rates = {}
    counts = {}
    for group in df[protected_col].dropna().unique():
        sub = df[df[protected_col] == group]
        if len(sub) == 0:
            continue
        rate = round(100 * (sub[outcome_col].astype(str).str.lower() == pos).sum() / len(sub), 1)
        rates[str(group)] = rate
        counts[str(group)] = len(sub)

    if len(rates) < 2:
        return {"available": False, "summary": "Need at least two groups to compute outcome gap."}

    max_group = max(rates, key=rates.get)
    min_group = min(rates, key=rates.get)
    max_rate = rates[max_group]
    min_rate = rates[min_group]

    ratio = round(min_rate / max_rate * 100, 1) if max_rate > 0 else 0
    verdict = "PASS" if ratio >= 80 else "FAIL"
    severity = "ok" if verdict == "PASS" else "crit"

    gap_pts = round(max_rate - min_rate, 1)

    if verdict == "PASS":
        title = "Outcomes look balanced"
        summary = (f"Across {protected_col}, the highest acceptance rate is {max_rate}% "
                   f"({max_group}) and the lowest is {min_rate}% ({min_group}). Ratio is {ratio}%, "
                   f"comfortably above the 80% threshold.")
        fix = "→ No action needed for this dimension."
    else:
        title = "The outcomes aren't equal"
        summary = (f"{max_group} group got a positive outcome {max_rate}% of the time. "
                   f"{min_group} got it only {min_rate}% of the time. That's a {gap_pts}-point gap "
                   f"the model will happily learn.")
        fix = "→ Use reweighting, or apply Fairlearn's fairness constraints during training."

    return {
        "available": True,
        "title": title,
        "summary": summary,
        "severity": severity,
        "rates": rates,
        "counts": counts,
        "max_group": max_group,
        "min_group": min_group,
        "max_rate": max_rate,
        "min_rate": min_rate,
        "ratio": ratio,
        "verdict": verdict,
        "rule_hint": f"{min_rate}/{max_rate} = {ratio}% (need ≥80%)",
        "outcome_col": outcome_col,
        "positive_value": pos,
        "fix": fix
    }


# ===========================================================
# MODULE 4 — Data quality
# ===========================================================
def analyze_quality(df: pd.DataFrame) -> dict:
    items = []
    for col in df.columns:
        non_null = df[col].notna() & (df[col].astype(str).str.strip() != "")
        pct = round(100 * non_null.sum() / len(df), 1)
        items.append({
            "name": str(col),
            "pct": f"{pct}%",
            "warn": bool(pct < 97)
        })

    avg = round(sum(float(i["pct"].replace("%", "")) for i in items) / len(items), 1)
    severity = "ok" if avg >= 95 else "warn"

    if severity == "ok":
        summary = f"{avg}% average completeness across columns. Nothing concerning."
        fix = "→ Looking good. Optionally impute small gaps."
    else:
        summary = f"Average completeness is {avg}%. A few columns have notable missingness."
        fix = "→ Investigate whether missingness correlates with any protected group."

    return {
        "available": True,
        "title": "Most fields are filled in" if severity == "ok" else "Data has noticeable gaps",
        "summary": summary,
        "severity": severity,
        "items": items[:8],
        "fix": fix
    }


# ===========================================================
# MASTER — overall bias score
# ===========================================================
SEVERITY_W = {"ok": 0.0, "warn": 0.4, "crit": 1.0}


def compute_score(rep, prox, gap, qual) -> tuple[float, str, str]:
    weights = {"rep": 0.25, "prox": 0.30, "gap": 0.35, "qual": 0.10}
    penalty = (
        SEVERITY_W.get(rep.get("severity", "ok"), 0) * weights["rep"] +
        SEVERITY_W.get(prox.get("severity", "ok"), 0) * weights["prox"] +
        SEVERITY_W.get(gap.get("severity", "ok"), 0) * weights["gap"] +
        SEVERITY_W.get(qual.get("severity", "ok"), 0) * weights["qual"]
    )
    score = round(10 * (1 - penalty), 1)
    score = max(0.0, min(10.0, score))

    if score >= 8:
        label, color = "Mostly fair", "#7A8C5F"
    elif score >= 6:
        label, color = "Needs attention", "#D4A574"
    elif score >= 4:
        label, color = "High risk", "#B7472A"
    else:
        label, color = "Critical bias", "#7A1F0F"
    return score, label, color


# ===========================================================
# Honest auditor note (human language)
# ===========================================================
def write_honest_note(score, rep, prox, gap) -> str:
    parts = []
    if rep.get("severity") in ("crit", "warn"):
        parts.append(f"the dataset leans heavily toward {rep['bars'][0]['label']}")
    if prox.get("severity") == "crit":
        top = prox["items"][0]
        parts.append(f"the column <strong>{top['col']}</strong> quietly carries {top['target']} information")
    if gap.get("severity") == "crit":
        parts.append(f"{gap.get('max_group')} gets a positive outcome {gap.get('max_rate')}% vs only {gap.get('min_rate')}% for {gap.get('min_group')}")

    if not parts:
        return ("Honestly? This dataset is in pretty good shape. If you train carefully, "
                "the resulting model has a real chance at being fair.")

    body = "; and ".join(parts)
    return (f"Here's what we noticed — {body}. Nothing is catastrophic on its own, "
            f"but if you trained a model today, certain people would be more likely to get a 'no' "
            f"before they ever got a fair look.")


# ===========================================================
# Public entrypoint
# ===========================================================
def audit_dataframe(df: pd.DataFrame, dataset_title: str = "Custom dataset") -> dict:
    detected = detect_columns(df)
    protected = detected["protected"]
    proxy_candidates = detected["proxy_suspects"]
    outcome = detected["outcome"]

    primary_protected = protected[0] if protected else None

    rep = analyze_representation(df, primary_protected)
    prox = analyze_proxies(df, protected, proxy_candidates)
    gap = analyze_gap(df, primary_protected, outcome)
    qual = analyze_quality(df)

    score, label, color = compute_score(rep, prox, gap, qual)
    honest = write_honest_note(score, rep, prox, gap)

    return {
        "title": f"{dataset_title} · {len(df)} rows",
        "meta": f"Audited just now · {len(df.columns)} columns reviewed",
        "score": score,
        "score_label": label,
        "score_color": color,
        "honest": honest,
        "detected": {
            "protected_columns": protected,
            "outcome_column": outcome,
            "proxy_candidates": proxy_candidates
        },
        "representation": rep,
        "proxies": prox,
        "gap": gap,
        "quality": qual,
    }


def audit_csv_bytes(file_bytes: bytes, title: str = "Uploaded dataset") -> dict:
    df = pd.read_csv(io.BytesIO(file_bytes))
    return audit_dataframe(df, title)

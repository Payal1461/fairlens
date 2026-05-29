"""
Fairlens — Flask backend (minimal)
Endpoints:
  GET  /                          → serves the frontend
  GET  /api/health
  GET  /api/samples               → list available sample datasets
  POST /api/audit/sample/<name>   → audit a built-in sample
  POST /api/audit/upload          → audit an uploaded CSV
  GET  /api/preview/<job_id>      → first 10 rows of an audited dataset
"""
import io
import os
import uuid
import numpy as np
import pandas as pd
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort

from audit_engine import audit_dataframe


def to_json_safe(obj):
    """Recursively convert numpy types to plain Python."""
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if pd.isna(obj) if not isinstance(obj, (dict, list, tuple, str)) else False:
        return None
    return obj


BASE = Path(__file__).parent
FRONTEND = BASE.parent  # serve index.html / styles.css / script.js
SAMPLES = BASE / "sample_data"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")

# in-memory store of audited datasets, used only by the preview endpoint
JOBS: dict = {}

SAMPLE_MAP = {
    "loan":   {"file": "loan_data.csv",       "title": "Loan Approvals"},
    "hire":   {"file": "hiring_data.csv",     "title": "Hiring Decisions"},
    "admit":  {"file": "admissions_data.csv", "title": "College Admissions"},
}


# ---------- frontend ----------
@app.route("/")
def index():
    return send_from_directory(str(FRONTEND), "index.html")


@app.route("/<path:path>")
def static_files(path):
    if (FRONTEND / path).exists():
        return send_from_directory(str(FRONTEND), path)
    abort(404)


# ---------- health ----------
@app.get("/api/health")
def health():
    return {"ok": True, "samples": list(SAMPLE_MAP.keys()), "jobs": len(JOBS)}


# ---------- samples ----------
@app.get("/api/samples")
def list_samples():
    out = []
    for key, meta in SAMPLE_MAP.items():
        p = SAMPLES / meta["file"]
        if p.exists():
            df = pd.read_csv(p)
            out.append({
                "key": key,
                "title": meta["title"],
                "file": meta["file"],
                "rows": len(df),
                "cols": len(df.columns),
            })
    return jsonify(out)


@app.post("/api/audit/sample/<name>")
def audit_sample(name):
    if name not in SAMPLE_MAP:
        return {"error": "Unknown sample"}, 404
    meta = SAMPLE_MAP[name]
    df = pd.read_csv(SAMPLES / meta["file"])
    return _run_audit(df, meta["title"])


# ---------- upload ----------
@app.post("/api/audit/upload")
def audit_upload():
    if "file" not in request.files:
        return {"error": "No file"}, 400
    f = request.files["file"]
    try:
        df = pd.read_csv(io.BytesIO(f.read()))
    except Exception as e:
        return {"error": f"Couldn't parse CSV: {e}"}, 400
    title = Path(f.filename).stem.replace("_", " ").title() or "Uploaded dataset"
    return _run_audit(df, title)


def _run_audit(df: pd.DataFrame, title: str):
    job_id = uuid.uuid4().hex[:10]
    result = audit_dataframe(df, title)
    JOBS[job_id] = {"df": df}  # kept only so /api/preview can show rows
    payload = dict(result)
    payload["job_id"] = job_id
    return jsonify(to_json_safe(payload))


# ---------- preview ----------
@app.get("/api/preview/<job_id>")
def preview(job_id):
    job = JOBS.get(job_id)
    if not job:
        return {"error": "job not found"}, 404
    df = job["df"].head(10)
    return jsonify({
        "columns": list(df.columns),
        "rows": df.fillna("").astype(str).values.tolist(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5057))
    print(f"\n  Fairlens running at http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)

/* ===========================================
   Fairlens — frontend wired to Flask backend
   (minimal: audit + findings + data preview)
   =========================================== */

const API = ""; // same origin
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

// ---------- DOM refs ----------
const startBtn = $("#startBtn");
const sampleBtn = $("#sampleBtn");
const dropzone = $("#dropzone");
const fileInput = $("#fileInput");
const dropHint = $("#dropHint");
const sampleChips = $$(".sample-chip");
const uploadSection = $("#upload");
const scanningSection = $("#scanning");
const resultsSection = $("#results");
const newAuditBtn = $("#newAuditBtn");

// ---------- interactions ----------
startBtn?.addEventListener("click", () => {
  uploadSection.scrollIntoView({ behavior: "smooth" });
});
sampleBtn?.addEventListener("click", () => runSample("loan"));

dropzone?.addEventListener("click", () => fileInput.click());
fileInput?.addEventListener("change", (e) => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
});

["dragover", "dragenter"].forEach(ev =>
  dropzone?.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--terracotta)";
    dropzone.style.background = "var(--paper)";
  })
);
["dragleave", "dragend"].forEach(ev =>
  dropzone?.addEventListener(ev, () => {
    dropzone.style.borderColor = "";
    dropzone.style.background = "";
  })
);
dropzone?.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.style.borderColor = "";
  dropzone.style.background = "";
  const f = e.dataTransfer.files[0];
  if (f) uploadFile(f);
});

sampleChips.forEach(chip =>
  chip.addEventListener("click", () => runSample(chip.dataset.sample))
);

newAuditBtn?.addEventListener("click", () => {
  resultsSection.style.display = "none";
  uploadSection.style.display = "block";
  uploadSection.scrollIntoView({ behavior: "smooth" });
});

// ---------- run audit (sample) ----------
async function runSample(key) {
  startScan();
  try {
    const res = await fetch(`${API}/api/audit/sample/${key}`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    await finishScan(data);
  } catch (err) {
    showError(err);
  }
}

// ---------- run audit (upload) ----------
async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    alert("Please upload a .csv file.");
    return;
  }
  dropHint.textContent = `Reading ${file.name}…`;
  startScan();
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(`${API}/api/audit/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    await finishScan(data);
  } catch (err) {
    showError(err);
  }
}

function showError(err) {
  scanningSection.style.display = "none";
  uploadSection.style.display = "block";
  alert("Audit failed: " + (err.message || err));
}

// ---------- scan animation ----------
function startScan() {
  uploadSection.style.display = "none";
  resultsSection.style.display = "none";
  scanningSection.style.display = "block";
  scanningSection.scrollIntoView({ behavior: "smooth" });

  const steps = $$(".scan-step");
  steps.forEach(s => s.classList.remove("active", "done"));
  const statusEl = $("#scanStatus");
  const messages = [
    "Reading rows…",
    "Looking for who's represented…",
    "Sniffing out hidden proxies…",
    "Measuring outcome gaps…",
    "Writing your report…"
  ];
  let i = 0;
  statusEl.textContent = messages[0];

  window._scanInterval = setInterval(() => {
    if (i > 0) {
      steps[i - 1].classList.remove("active");
      steps[i - 1].classList.add("done");
    }
    if (i < steps.length) {
      steps[i].classList.add("active");
      statusEl.textContent = messages[i + 1] || messages[messages.length - 1];
      i++;
    } else {
      clearInterval(window._scanInterval);
    }
  }, 700);
}

async function finishScan(data) {
  // ensure scan animation plays at least 2.4s
  await sleep(2400);
  clearInterval(window._scanInterval);
  $$(".scan-step").forEach(s => s.classList.add("done"));
  await sleep(500);

  scanningSection.style.display = "none";
  renderResults(data);
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ---------- render audit result ----------
function renderResults(data) {
  $("#reportTitle").textContent = data.title;
  $("#reportMeta").textContent = data.meta;
  $("#scoreNum").textContent = data.score.toFixed(1);
  $("#scoreLabel").textContent = data.score_label;
  $("#scoreRing").style.borderColor = data.score_color;
  $("#honestText").innerHTML = data.honest;

  const grid = $(".findings-grid");
  grid.innerHTML = buildFindings(data);

  resultsSection.style.display = "block";
  resultsSection.scrollIntoView({ behavior: "smooth" });

  // animate bars
  setTimeout(() => {
    $$(".bar-fill").forEach(el => {
      if (el.dataset.width) el.style.width = el.dataset.width + "%";
    });
    $$(".gap-fill").forEach(el => {
      if (el.dataset.height) el.style.height = el.dataset.height + "%";
    });
  }, 50);

  // load the data preview
  loadPreview(data.job_id);
}

function buildFindings(data) {
  const r = data.representation;
  const p = data.proxies;
  const g = data.gap;
  const q = data.quality;

  let html = "";

  // representation
  if (r.available) {
    html += `
    <article class="finding-card severity-${r.severity}">
      <div class="finding-top">
        <span class="finding-num">01</span>
        <span class="finding-tag">Representation · ${escapeHtml(r.column)}</span>
      </div>
      <h3 class="finding-title">${escapeHtml(r.title)}</h3>
      <p class="finding-body">${r.summary}</p>
      <div class="bars">
        ${r.bars.map(b => `
          <div class="bar-row">
            <span class="bar-label">${escapeHtml(b.label)}</span>
            <div class="bar"><div class="bar-fill ${b.class}" data-width="${b.value}" style="width:0%"></div></div>
            <span class="bar-val">${b.value}%</span>
          </div>
        `).join("")}
      </div>
      <p class="finding-fix">${escapeHtml(r.fix)}</p>
    </article>`;
  }

  // proxies
  if (p.available) {
    html += `
    <article class="finding-card severity-${p.severity}">
      <div class="finding-top">
        <span class="finding-num">02</span>
        <span class="finding-tag">Hidden proxies</span>
      </div>
      <h3 class="finding-title">${escapeHtml(p.title)}</h3>
      <p class="finding-body">${p.summary}</p>
      <div class="proxy-list">
        ${p.items.map(i => `
          <div class="proxy-item">
            <span class="proxy-col">${escapeHtml(i.col)}</span>
            <span class="proxy-arrow">→</span>
            <span class="proxy-target">${escapeHtml(i.target)}</span>
            <span class="proxy-score ${i.severity}">${escapeHtml(i.score_label)}</span>
          </div>
        `).join("") || `<p class="cf-empty">No suspicious columns. Clean.</p>`}
      </div>
      <p class="finding-fix">${escapeHtml(p.fix)}</p>
    </article>`;
  }

  // gap
  if (g.available) {
    const ratesArr = Object.entries(g.rates);
    const top2 = ratesArr.sort((a, b) => b[1] - a[1]).slice(0, 2);
    html += `
    <article class="finding-card severity-${g.severity}">
      <div class="finding-top">
        <span class="finding-num">03</span>
        <span class="finding-tag">Outcome gap</span>
      </div>
      <h3 class="finding-title">${escapeHtml(g.title)}</h3>
      <p class="finding-body">${g.summary}</p>
      <div class="gap-viz">
        ${top2.map(([name, rate], idx) => `
          <div class="gap-col">
            <div class="gap-bar"><div class="gap-fill ${idx === 0 ? 'male' : 'female'}" data-height="${rate}" style="height:0%"></div></div>
            <p class="gap-pct">${rate}%</p>
            <p class="gap-lbl">${escapeHtml(name)}</p>
          </div>
        `).join("")}
        <div class="gap-col">
          <p class="gap-rule">⚖️ 80% rule</p>
          <p class="gap-rule-val" style="color:${g.verdict === 'PASS' ? 'var(--sage)' : 'var(--crit)'}">${g.verdict}</p>
          <p class="gap-rule-hint">${escapeHtml(g.rule_hint)}</p>
        </div>
      </div>
      <p class="finding-fix">${escapeHtml(g.fix)}</p>
    </article>`;
  } else {
    html += `
    <article class="finding-card severity-ok">
      <div class="finding-top">
        <span class="finding-num">03</span>
        <span class="finding-tag">Outcome gap</span>
      </div>
      <h3 class="finding-title">Couldn't compute</h3>
      <p class="finding-body">${escapeHtml(g.summary || 'No outcome column detected.')}</p>
    </article>`;
  }

  // quality
  html += `
  <article class="finding-card severity-${q.severity}">
    <div class="finding-top">
      <span class="finding-num">04</span>
      <span class="finding-tag">Data quality</span>
    </div>
    <h3 class="finding-title">${escapeHtml(q.title)}</h3>
    <p class="finding-body">${escapeHtml(q.summary)}</p>
    <div class="quality-list">
      ${q.items.map(i => `
        <div class="quality-item">
          <span>${escapeHtml(i.name)}</span>
          <span class="quality-val ${i.warn ? 'warn' : ''}">${escapeHtml(i.pct)}</span>
        </div>
      `).join("")}
    </div>
    <p class="finding-fix">${escapeHtml(q.fix)}</p>
  </article>`;

  return html;
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// ---------- preview table ----------
async function loadPreview(jobId) {
  try {
    const res = await fetch(`${API}/api/preview/${jobId}`);
    const data = await res.json();
    const tbl = $("#dataTable");
    tbl.innerHTML = `
      <thead><tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>
      <tbody>
        ${data.rows.map(row => `<tr>${row.map(v => `<td>${escapeHtml(v)}</td>`).join("")}</tr>`).join("")}
      </tbody>
    `;
  } catch (e) {
    console.error("preview failed", e);
  }
}

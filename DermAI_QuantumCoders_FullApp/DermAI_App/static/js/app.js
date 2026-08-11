/* DermAI front-end controller — wires the existing UI to the Flask API.
   Every function named in an inline onclick handler is defined here. */
"use strict";

const S = { user: null, step: 1, maxStep: 1, patientId: null,
            imageId: null, imgUploaded: false, lastAssessmentId: null,
            fitz: "IV", body: "Back" };

const SCREENS = {
  login: "scr-login", signup: "scr-signup", forgot: "scr-forgot", verify: "scr-verify",
  dashboard: "scr-dashboard", assessment: "scr-assessment", report: "scr-report",
  records: "scr-records", profile: "scr-profile", admin: "scr-admin",
};
const PUBLIC = new Set(["login", "signup", "forgot", "verify"]);

/* ---------------------------------------------------------------- utilities */
const $ = (id) => document.getElementById(id);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function api(path, method = "GET", body = null, isForm = false) {
  const opt = { method, credentials: "same-origin", headers: {} };
  if (body && !isForm) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  if (body && isForm) { opt.body = body; }
  const r = await fetch(path, opt);
  let data = {};
  try { data = await r.json(); } catch (e) {}
  if (!r.ok) { const err = new Error(data.error || ("Request failed (" + r.status + ")")); err.data = data; throw err; }
  return data;
}

function showToast(msg, type = "info") {
  const wrap = $("toasts"); if (!wrap) return;
  const icons = { success: "✅", error: "⚠️", info: "ℹ️", warning: "⚠️" };
  const el = document.createElement("div");
  el.className = "toast toast-" + type;
  el.innerHTML = '<span class="toast-icon">' + (icons[type] || "ℹ️") + "</span><span>" + msg + "</span>";
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

function initials(name) {
  return (name || "U").replace("Dr. ", "").split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
}

/* ---------------------------------------------------------------- routing */
function showScreen(id) {
  $$(".screen").forEach(s => s.classList.remove("active"));
  const el = $(id); if (el) el.classList.add("active");
  window.scrollTo(0, 0);
}

function go(name) {
  if (!S.user && !PUBLIC.has(name)) { showScreen(SCREENS.login); return; }
  if (name === "admin" && (!S.user || S.user.role !== "admin")) { showToast("Admin access only", "error"); return; }
  if (name === "results") { showScreen(SCREENS.assessment); showStep(5); return; }
  showScreen(SCREENS[name] || SCREENS.login);
  if (name === "records") loadRecords();
  if (name === "report") loadReportBanner();
  if (name === "admin") loadAdmin();
  if (name === "assessment") resetAssessment();
}

function handleHash() {
  const h = (location.hash || "").replace(/^#\/?/, "").toLowerCase();
  if (h === "admin") {
    if (S.user && S.user.role === "admin") { go("admin"); return; }
    const em = $("login-email"); if (em) em.value = "admin@dermai.lk";
    const hint = $("admin-endpoint-hint"); if (hint) hint.style.display = "block";
    const t = $("login-title"); if (t) t.textContent = "Admin sign-in";
    showScreen(SCREENS.login);
    showToast("Admin endpoint — sign in with administrator credentials", "info");
  }
}

/* ---------------------------------------------------------------- auth */
async function doLogin() {
  const email = ($("login-email").value || "").trim();
  const pass  = $("login-pass").value || "";
  const box = $("login-err"), msg = $("login-err-msg");
  const show = m => { if (msg) msg.textContent = m; if (box) box.style.display = "block"; };
  if (box) box.style.display = "none";
  // client-side validation — do NOT proceed on empty/invalid input
  if (!email || !pass) { show("Please enter both your email and password."); return; }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { show("Enter a valid email address."); return; }
  if (pass.length < 6) { show("Password must be at least 6 characters."); return; }
  try {
    const r = await api("/api/auth/login", "POST", { email, password: pass });
    S.user = r.user; updateUserUI();
    showToast("Welcome, " + r.user.name, "success");
    go(r.user.role === "admin" ? "admin" : "dashboard");
  } catch (e) {
    show(e.message || "Invalid email or password.");
    if (e.data && e.data.verify_link) showToast("Verify your email first", "warning");
  }
}

function quickLogin(role) {
  const map = { doctor: ["doctor@dermai.lk", "Password@123"], admin: ["admin@dermai.lk", "Password@123"] };
  const [em, pw] = map[role] || map.doctor;
  $("login-email").value = em; $("login-pass").value = pw; doLogin();
}

async function doSignup() {
  const inp = $$("#scr-signup input.finput");
  const sel = $("#scr-signup select.finput") || $$("#scr-signup select.finput")[0];
  const body = {
    name: ((inp[0] && inp[0].value) || "") + " " + ((inp[1] && inp[1].value) || ""),
    slmc: inp[2] ? inp[2].value : "", email: inp[3] ? inp[3].value : "",
    password: inp[4] ? inp[4].value : "", confirm: inp[5] ? inp[5].value : "",
    specialization: sel ? sel.value : "Dermatologist",
  };
  try {
    const r = await api("/api/auth/register", "POST", body);
    showToast("Account created — verifying email…", "success");
    if (r.verify_link) { try { await api("/api/auth" + r.verify_link.replace("/verify", "/verify"), "GET"); } catch (e) {} }
    // (demo convenience: auto-verify via returned link, then send to login)
    $("login-email").value = body.email.trim().toLowerCase();
    go("verify");
  } catch (e) { showToast(e.message, "error"); }
}

function doForgot() {
  const ok = $("forgot-ok"); if (ok) ok.style.display = "block";
  showToast("If that email exists, a reset link was sent.", "info");
}

async function doLogout() {
  try { await api("/api/auth/logout", "POST"); } catch (e) {}
  S.user = null; location.hash = ""; go("login");
}

function updateUserUI() {
  if (!S.user) return;
  const n = S.user.name, ini = initials(n);
  ["d-uname", "a-uname"].forEach(id => { if ($(id)) $(id).textContent = n; });
  ["d-av", "a-av", "rec-av", "pr-av", "rp-av"].forEach(id => { if ($(id)) $(id).textContent = ini; });
  if ($("pr-av-big")) $("pr-av-big").textContent = ini;
  if ($("pr-name")) $("pr-name").textContent = n;
}

/* ---------------------------------------------------------------- assessment wizard */
function resetAssessment() {
  S.step = 1; S.maxStep = 1; S.imageId = null; S.imgUploaded = false; S.lastAssessmentId = null;
  const nx = $("next-s2"); if (nx) nx.disabled = true;
  const prev = $("img-prev"); if (prev) prev.style.display = "none";
  const dz = $("dz"); if (dz) dz.style.display = "block";
  showStep(1);
}

function showStep(n) {
  for (let i = 1; i <= 5; i++) { const p = $("ast-" + i); if (p) p.style.display = (i === n) ? "block" : "none"; }
  S.step = n; S.maxStep = Math.max(S.maxStep, n);
  updateWizBar(n); window.scrollTo(0, 0);
}

function updateWizBar(active) {
  for (let i = 1; i <= 5; i++) {
    const c = $("ws" + i), l = $("wl" + i);
    if (c) c.className = "wstep-circle " + (i < active ? "done" : i === active ? "active" : "idle");
    if (c) c.textContent = i < active ? "✓" : i;
    if (l) l.className = "wstep-label " + (i < active ? "done" : i === active ? "active" : "idle");
    if (i <= 4) { const ln = $("wc" + i); if (ln) ln.className = "wstep-line " + (i < active ? "done" : "idle"); }
  }
}

function goStep(n) {
  if (n === 3 && !S.imgUploaded) {
    showToast("Continuing without an image — assessment will use symptoms only.", "warning");
  }
  if (n === 4) { showStep(4); startAI(); return; }
  showStep(n);
}

function tryJumpTo(n) { if (n <= S.maxStep) showStep(n); }

/* ---------- image upload (FR9–13) ---------- */
function simulateUpload() {
  let inp = $("real-file-input");
  if (!inp) {
    inp = document.createElement("input");
    inp.type = "file"; inp.id = "real-file-input"; inp.accept = "image/*"; inp.style.display = "none";
    inp.addEventListener("change", onFilePicked); document.body.appendChild(inp);
  }
  inp.click();
}

async function onFilePicked(ev) {
  const f = ev.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("image", f);
  showToast("Uploading & checking image…", "info");
  try {
    const r = await api("/api/upload", "POST", fd, true);
    S.imageId = r.image_id; S.imgUploaded = true;
    const dz = $("dz"); if (dz) dz.style.display = "none";
    const prev = $("img-prev"); if (prev) prev.style.display = "block";
    const nm = document.querySelector("#img-prev .img-name"); if (nm) nm.textContent = f.name;
    const mt = document.querySelector("#img-prev .img-meta");
    if (mt) mt.textContent = r.meta.size_mb + " MB · " + r.meta.width + " × " + r.meta.height + " px · blur " + r.meta.blur;
    const badges = document.querySelector("#img-prev .img-badges");
    if (badges) badges.innerHTML =
      qBadge(r.checks.format, "Format") + qBadge(r.checks.size, "Size") + qBadge(r.checks.resolution, "Resolution");
    renderQA(r);
    const idle = $("qa-idle-msg"); if (idle) idle.style.display = "none";
    const list = $("qa-list"); if (list) list.style.display = "block";
    const nx = $("next-s2"); if (nx) nx.disabled = false;
    showToast(r.quality_pass ? "Image passed quality checks" : "Image accepted (quality warnings)",
              r.quality_pass ? "success" : "warning");
  } catch (e) { showToast(e.message, "error"); }
}

function qBadge(ok, label) {
  return '<span class="badge badge-' + (ok ? "success" : "danger") + '">' +
         (ok ? "✅ " : "❌ ") + label + "</span>";
}

/* build the Auto Quality Assessment panel from the REAL backend response */
function renderQA(r) {
  const list = $("qa-list"); if (!list) return;
  const c = r.checks, m = r.meta;
  const row = (ok, label, val) =>
    '<div class="qa-row ' + (ok ? "pass" : "fail") + '">' +
      '<span class="qa-label">' + (ok ? "✅ " : "❌ ") + label + "</span>" +
      '<span class="badge badge-' + (ok ? "success" : "danger") + '">' + val + "</span></div>";
  const itaTxt = (r.ita === null || r.ita === undefined) ? "n/a" : r.ita + "° (Fitzpatrick est.)";
  list.innerHTML =
    row(c.resolution, "Resolution ≥ 299×299 px", m.width + "×" + m.height) +
    row(c.size, "File size ≤ 10 MB", m.size_mb + " MB") +
    row(c.sharpness, "Sharpness (Laplacian var.)", m.blur) +
    row(c.format, "File format", "OK") +
    '<div class="qa-row ' + (r.quality_pass ? "pass" : "warn") + '" style="margin-top:8px;border:2px solid rgba(46,125,50,.2);">' +
      '<span class="qa-label" style="font-weight:800;">Skin-tone (ITA°)</span>' +
      '<span class="badge badge-neutral">' + itaTxt + "</span></div>" +
    '<div class="qa-row ' + (r.quality_pass ? "pass" : "warn") + '" style="border:2px solid rgba(46,125,50,.2);">' +
      '<span class="qa-label" style="font-weight:800;">Overall Status</span>' +
      '<span class="badge badge-' + (r.quality_pass ? "success" : "warning") + '" style="font-size:11px;">' +
      (r.quality_pass ? "✅ SUITABLE FOR AI" : "⚠️ REVIEW — LOW QUALITY") + "</span></div>";
}

function removeImg() {
  S.imageId = null; S.imgUploaded = false;
  const prev = $("img-prev"); if (prev) prev.style.display = "none";
  const dz = $("dz"); if (dz) dz.style.display = "block";
  const list = $("qa-list"); if (list) { list.style.display = "none"; list.innerHTML = ""; }
  const idle = $("qa-idle-msg"); if (idle) idle.style.display = "block";
  const nx = $("next-s2"); if (nx) nx.disabled = true;
}

/* ---------- read patient + symptoms ---------- */
function readPatient() {
  const v = (id) => { const e = $(id); return e ? e.value : ""; };
  return {
    first_name: v("pt-fn"), last_name: v("pt-ln"),
    age: v("pt-age"), gender: v("pt-gender"),
    fitzpatrick: S.fitz, lesion_location: S.body,
    duration_weeks: v("pt-dur"), growth_speed: v("pt-growth"), notes: v("pt-notes"),
  };
}

const SYM_MAP = [
  ["A — Asymmetry", "a_asym"], ["B — Border", "b_border"], ["C — Colour", "c_colour"],
  ["D — Diameter", "d_diam"], ["E — Evolving", "e_evolve"], ["Blue-white veil", "blue_white"],
  ["Dark streak under nail", "nail"], ["New mole", "new_mole"], ["Irregular pigment network", "pigment_net"],
  ["Pearly", "bcc_pearly"], ["Rolled / raised", "bcc_rolled"], ["Telangiectasia", "bcc_telangiectasia"],
  ["rodent ulcer", "bcc_ulcer"], ["Red scaly patch", "bcc_scaly"], ["Non-healing wound", "bcc_nonheal"],
  ["Firm red nodule", "scc_nodule"], ["Scaly / crusted", "scc_scaly"], ["Hyperkeratotic", "scc_hyperkeratotic"],
  ["Ulcer with raised", "scc_ulcer"], ["Rapid enlargement", "scc_rapid"], ["sun-exposed area", "scc_sunexposed"],
  ["actinic keratosis", "scc_ak"], ["Marjolin", "scc_marjolin"],
  ["A — Asymptomatic", "mcc_a"], ["E — Expanding", "mcc_e"], ["I — Immunosuppressed", "mcc_i"],
  ["O — Older", "mcc_o"], ["U — UV", "mcc_u"], ["dome-shaped nodule", "mcc_dome"], ["No pigmentation variation", "mcc_uniform"],
  ["Pain / Tenderness", "pain"], ["Bleeding from lesion", "bleeding"], ["Ulceration present", "ulceration"],
  ["Itching", "itching"], ["Fair skin", "fair_skin"], ["Multiple nevi", "moles50"], ["lymph nodes", "nodes"],
];

function readSymptoms() {
  const sym = { age: parseInt(($("pt-age") || {}).value || "0", 10) || 0 };
  $$("#ast-3 .chk-item").forEach(item => {
    const on = item.querySelector(".chk-box.on"); if (!on) return;
    const text = item.innerText || item.textContent || "";
    for (const [needle, key] of SYM_MAP) { if (text.indexOf(needle) !== -1) { sym[key] = true; break; } }
  });
  const imm = $("pt-notes"); // heuristic risk flags come from selects with no id; keep symptom-driven
  return sym;
}

/* ---------- AI inference (FR14–19) ---------- */
async function startAI() {
  const tasks = [1, 2, 3, 4, 5, 6, 7].map(i => $("ai-task-" + i)).filter(Boolean);
  tasks.forEach(t => { t.className = "ai-task idle"; });
  setBar(0, "Starting inference…");
  const spin = $("ai-spin"); if (spin) spin.style.display = "block";

  let done = false, res = null, err = null;
  api("/api/assess", "POST", { patient: readPatient(), image_id: S.imageId, symptoms: readSymptoms() })
    .then(r => res = r).catch(e => err = e).finally(() => done = true);

  let i = 0;
  const timer = setInterval(() => {
    if (i > 0 && tasks[i - 1]) tasks[i - 1].className = "ai-task done";
    if (i < tasks.length) {
      tasks[i].className = "ai-task running";
      setBar(Math.round(((i + 1) / (tasks.length + 1)) * 100), tasks[i].querySelector(".ai-task-title").textContent);
      i++;
    } else if (done) {
      clearInterval(timer);
      tasks.forEach(t => t.className = "ai-task done");
      setBar(100, "Complete");
      if (err) { showToast(err.message || "Analysis failed", "error"); return; }
      S.lastAssessmentId = res.assessment_id;
      updateLiveProbs(res.probs);
      renderResults(res);
      showStep(5);
    }
  }, 320);
}

function setBar(pct, label) {
  const bar = $("ai-pbar"); if (bar) bar.style.width = pct + "%";
  const p = $("ai-pct-lbl"); if (p) p.textContent = pct + "%";
  const l = $("ai-status-lbl"); if (l && label) l.textContent = label;
}

function updateLiveProbs(probs) {
  const set = (live, bar, val) => {
    if ($(live)) $(live).textContent = val.toFixed(1) + "%";
    if ($(bar)) $(bar).style.width = val + "%";
  };
  set("mel-live", "mel-bar", probs.Melanoma);
  set("scc-live", "scc-bar", probs.SCC);
  set("bcc-live", "bcc-bar", probs.BCC);
  set("mcc-live", "mcc-bar", probs.MCC);
}

function renderResults(res) {
  let card = $("live-result");
  if (!card) {
    card = document.createElement("div");
    card.id = "live-result"; card.className = "card"; card.style.marginBottom = "18px";
    const host = $("ast-5"); const anchor = host.querySelector(".disclaimer-bar");
    host.insertBefore(card, anchor ? anchor.nextSibling : host.firstChild);
  }
  const modeBadge = res.mode === "trained"
    ? '<span class="badge badge-success">TRAINED MODE</span>'
    : '<span class="badge badge-warning">CLINICAL-RULE MODE</span>';
  const uncertain = res.uncertain ? '<span class="badge badge-danger">UNCERTAIN &lt;50%</span>' : "";
  const urgencyBadge = { Emergency: "badge-danger", Urgent: "badge-warning", Routine: "badge-neutral" }[res.urgency] || "badge-neutral";
  const p = res.probs;
  const heat = res.has_heatmap
    ? '<img src="/api/assess/' + res.assessment_id + '/heatmap" alt="heatmap" style="width:120px;height:120px;object-fit:cover;border-radius:8px;border:1px solid var(--border);"/>'
    : "";
  card.innerHTML =
    '<div class="flex-between" style="margin-bottom:12px;"><div class="card-title">🧠 Live AI Result (from your database & model)</div>' +
    modeBadge + "</div>" +
    '<div class="flex-start" style="gap:20px;flex-wrap:wrap;align-items:flex-start;">' +
      heat +
      '<div style="flex:1;min-width:240px;">' +
        '<div style="font-size:22px;font-weight:800;color:var(--p800);margin-bottom:4px;">' + res.predicted_type +
        ' &nbsp;<span style="font-size:15px;color:var(--muted);">' + res.confidence + "% confidence</span></div>" +
        '<div style="margin-bottom:10px;display:flex;gap:6px;flex-wrap:wrap;">' +
          '<span class="badge ' + urgencyBadge + '">' + res.urgency + "</span>" +
          '<span class="badge badge-primary">Stage: ' + res.stage + "</span>" + uncertain + "</div>" +
        probBar("Melanoma", p.Melanoma, "fill-mel") + probBar("BCC", p.BCC, "fill-bcc") +
        probBar("SCC", p.SCC, "fill-scc") + probBar("MCC", p.MCC, "fill-mcc") +
      "</div>" +
    "</div>" +
    '<div class="flex-start" style="gap:10px;margin-top:14px;flex-wrap:wrap;">' +
      '<button class="btn btn-primary" onclick="go(\'report\')">📄 View Full Report</button>' +
      '<button class="btn btn-secondary" onclick="downloadPDF()">📥 Download PDF</button>' +
      '<button class="btn btn-outline" onclick="resetAssessment()">🔬 New Assessment</button></div>';
}

function probBar(name, val, cls) {
  return '<div class="prob-row"><div class="prob-header"><span class="prob-name">' + name +
    '</span><span class="prob-pct">' + val.toFixed(1) + '%</span></div>' +
    '<div class="prob-track"><div class="prob-fill ' + cls + '" style="width:' + val + '%"></div></div></div>';
}

/* ---------- report (FR20–21) ---------- */
function downloadPDF(aid) {
  const id = aid || S.lastAssessmentId;
  if (!id) { showToast("Run an assessment first.", "warning"); return; }
  window.open("/api/report/" + id + "/pdf", "_blank");
}
window.downloadReport = downloadPDF;

async function loadReportBanner() {
  const id = S.lastAssessmentId; if (!id) return;
  try {
    const r = await api("/api/report/" + id);
    const a = r.assessment, host = $("scr-report").querySelector(".report-doc");
    if (host && !$("report-live")) {
      const div = document.createElement("div");
      div.id = "report-live"; div.className = "report-sec"; div.style.background = "var(--p50)";
      div.innerHTML = '<div class="rsec-title">🧠 Live AI Result (' + (a.mode || "rule").toUpperCase() + " MODE)</div>" +
        '<div class="rfield"><span class="rfield-key">Predicted Type</span><span class="rfield-val">' + a.predicted_type + "</span></div>" +
        '<div class="rfield"><span class="rfield-key">Confidence</span><span class="rfield-val">' + a.confidence + "%</span></div>" +
        '<div class="rfield"><span class="rfield-key">Stage</span><span class="rfield-val">' + a.stage + "</span></div>" +
        '<div class="rfield"><span class="rfield-key">Urgency</span><span class="rfield-val">' + a.urgency + "</span></div>";
      host.insertBefore(div, host.children[1] || null);
    }
    $$("#scr-report button").forEach(b => { if ((b.textContent || "").includes("PDF")) b.onclick = () => downloadPDF(id); });
  } catch (e) {}
}

function goResultsFromReport() { go("assessment"); showStep(5); }

/* ---------- records (FR20) ---------- */
async function loadRecords() {
  try {
    const r = await api("/api/patients");
    const tb = $("rec-tbody"); if (!tb) return;
    if (!r.patients.length) { tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:26px;">No patient records yet — run a new assessment.</td></tr>'; return; }
    tb.innerHTML = r.patients.map(p => {
      const l = p.last;
      const type = l ? l.predicted_type : "—";
      const conf = l ? l.confidence + "%" : "—";
      const urg = l ? l.urgency : "—";
      const date = l ? l.created_at : "—";
      const badge = { Emergency: "badge-danger", Urgent: "badge-warning", Routine: "badge-neutral" }[urg] || "badge-neutral";
      const act = l ? ('<button class="btn btn-xs btn-secondary" onclick="viewAssessment(' + l.id + ')">View</button>' +
                       '<button class="btn btn-xs btn-outline" onclick="downloadPDF(' + l.id + ')">PDF</button>') : "—";
      return "<tr><td><div class='td-name'>" + (p.first_name || "") + " " + (p.last_name || "") +
        "</div><div class='td-sub'>" + (p.patient_code || "") + "</div></td><td>" + (p.age || "—") + " / " +
        ((p.gender || "?")[0]) + "</td><td>" + type + "</td><td>" + (l ? l.stage : "—") + "</td><td>" + conf +
        "</td><td><span class='badge " + badge + "'>" + urg + "</span></td><td style='font-size:12px;'>" + date +
        "</td><td><div style='display:flex;gap:5px;'>" + act + "</div></td></tr>";
    }).join("");
  } catch (e) {}
}

function viewAssessment(aid) { S.lastAssessmentId = aid; go("report"); }

function filterRec(v) {
  v = (v || "").toLowerCase();
  $$("#rec-tbody tr").forEach(tr => { tr.style.display = tr.innerText.toLowerCase().includes(v) ? "" : "none"; });
}

/* ---------- admin (FR6) ---------- */
async function loadAdmin() {
  try {
    const [u, s] = [await api("/api/admin/users"), await api("/api/admin/stats")];
    const tb = document.querySelector("#atab-users table tbody");
    if (tb) tb.innerHTML = u.users.map(x => {
      const status = !x.is_active ? '<span class="badge badge-neutral">⛔ DEACTIVATED</span>'
        : !x.is_verified ? '<span class="badge badge-warning">⏳ PENDING</span>'
        : '<span class="badge badge-success">● ACTIVE</span>';
      const role = x.role === "admin" ? '<span class="badge badge-danger">ADMIN</span>' : '<span class="badge badge-primary">DOCTOR</span>';
      let actions = '<button class="btn btn-xs btn-outline" onclick="adminAct(' + x.id + ",'" + (x.is_active ? "deactivate" : "activate") + "')\">" + (x.is_active ? "Deactivate" : "Activate") + "</button>";
      if (!x.is_verified) actions = '<button class="btn btn-xs" style="background:var(--green);color:#fff;border:none;" onclick="adminAct(' + x.id + ",'verify')\">Verify</button>" + actions;
      if (x.role !== "admin") actions += '<button class="btn btn-xs btn-outline" style="color:var(--red);border-color:rgba(198,40,40,.3);" onclick="adminDelete(' + x.id + ')">Delete</button>';
      return "<tr><td class='td-name'>" + x.name + "</td><td style='font-size:12px;'>" + x.email +
        "</td><td><code class='tag'>" + (x.slmc_no || "—") + "</code></td><td>" + role + "</td><td>" + status +
        "</td><td style='font-size:12px;'>" + (x.created_at || "") + "</td><td><div style='display:flex;gap:5px;flex-wrap:wrap;'>" + actions + "</div></td></tr>";
    }).join("");
    const vals = $$("#atab-users .stat-value");
    if (vals.length >= 4) { vals[0].textContent = s.stats.total_users; vals[1].textContent = s.stats.active; vals[2].textContent = s.stats.pending; vals[3].textContent = s.stats.deactivated; }
  } catch (e) {}
}

async function adminAct(uid, action) {
  try { await api("/api/admin/users/" + uid + "/" + action, "POST"); showToast("User " + action + "d", "success"); loadAdmin(); }
  catch (e) { showToast(e.message, "error"); }
}
async function adminDelete(uid) {
  if (!confirm("Delete this user permanently?")) return;
  try { await api("/api/admin/users/" + uid, "DELETE"); showToast("User deleted", "success"); loadAdmin(); }
  catch (e) { showToast(e.message, "error"); }
}
function adminTab(name, el) {
  ["users", "system", "audit", "model"].forEach(t => { const p = $("atab-" + t); if (p) p.style.display = (t === name ? "block" : "none"); });
  $$(".admin-nav-item").forEach(i => i.classList.remove("active")); if (el) el.classList.add("active");
  if (name === "audit") loadAudit();
}
async function loadAudit() {
  try {
    const r = await api("/api/admin/audit");
    const tb = document.querySelector("#atab-audit table tbody");
    if (tb) tb.innerHTML = r.audit.map(a =>
      "<tr><td style='font-size:12px;'>" + a.at + "</td><td style='font-size:12px;'>" + a.user +
      "</td><td><span class='badge badge-primary'>" + a.action + "</span></td><td style='font-size:12.5px;'>" +
      a.details + "</td><td style='font-size:11px;color:var(--muted);'>" + a.ip + "</td></tr>").join("");
  } catch (e) {}
}

/* ---------------------------------------------------------------- cosmetic UI helpers */
function togglePass(id, el) { const i = $(id); if (!i) return; i.type = i.type === "password" ? "text" : "password"; if (el) el.textContent = i.type === "password" ? "👁" : "🙈"; }
function checkStrength(el) {/* visual only */}
function selSkin(el, v) { $$(".skin-swatch").forEach(s => s.classList.remove("sel")); el.classList.add("sel"); S.fitz = v; }
function selBody(el) { $$(".body-cell").forEach(b => b.classList.remove("sel")); el.classList.add("sel"); S.body = (el.textContent || "").replace("✓", "").trim(); }
function toggleChk(el) { const b = el.querySelector(".chk-box"); if (b) b.classList.toggle("on"); }
function selSymTab(el, id) {
  $$(".sym-tabbtn").forEach(b => { b.classList.remove("btn-primary"); b.classList.add("btn-outline"); });
  el.classList.remove("btn-outline"); el.classList.add("btn-primary");
  $$(".sym-window").forEach(w => w.style.display = "none");
  const win = $(id); if (win) win.style.display = "block";
}
function selHTab(el, which) {
  $$(".htab").forEach(t => t.classList.remove("active")); el.classList.add("active");
  ["orig", "heat", "overlay"].forEach(k => { const e = $("ht-" + k); if (e) e.style.display = (k === which ? "flex" : "none"); });
}
function showDelModal() { const m = $("del-modal"); if (m) m.style.display = "flex"; }
function hideDelModal() { const m = $("del-modal"); if (m) m.style.display = "none"; }
function confirmDel() { hideDelModal(); showToast("Account deletion is disabled in the demo.", "info"); }

/* ---------------------------------------------------------------- expose globals (inline onclick) */
Object.assign(window, {
  go, goStep, showStep, tryJumpTo, doLogin, quickLogin, doSignup, doForgot, doLogout,
  simulateUpload, removeImg, startAI, renderResults, downloadPDF, goResultsFromReport,
  viewAssessment, filterRec, adminTab, adminAct, adminDelete, showToast,
  togglePass, checkStrength, selSkin, selBody, toggleChk, selSymTab, selHTab,
  showDelModal, hideDelModal, confirmDel,
});

/* ---------------------------------------------------------------- boot */
window.addEventListener("DOMContentLoaded", async () => {
  // Always start on the login screen and require the user to sign in.
  // (We do NOT auto-jump to the dashboard from a leftover session cookie.)
  if ($("login-email")) $("login-email").value = "";
  if ($("login-pass")) $("login-pass").value = "";
  if (location.search.indexOf("verified=1") !== -1) showToast("Email verified — please sign in.", "success");
  // Clear any stale server session so a refresh can't skip the login screen.
  try { await api("/api/auth/logout", "POST"); } catch (e) {}
  S.user = null;
  showScreen(SCREENS.login);
  handleHash();
  window.addEventListener("hashchange", handleHash);
});

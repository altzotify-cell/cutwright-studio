/* Recap Studio — frontend */
"use strict";

const state = {
  bootstrap: null,
  projects: [],
  current: null,     // project name
  detail: null,
  segments: { youtube: [], tiktok: {} },
  missing: [],
  tab: "dashboard",
};

let activeJob = null;
let shownLines = 0;

const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function fmtBytes(n) {
  if (n == null) return "";
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
  return (n / 1073741824).toFixed(2) + " GB";
}

function wordsToSec(text) {
  const words = (text || "").split(/\s+/).filter(Boolean).length;
  return Math.round((words / 2.5) * 10) / 10;
}

async function apiGet(path) {
  const r = await fetch(path);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return r.json();
}

function enc(p) { return encodeURIComponent(p); }

function fileUrl(rel) {
  const segs = String(rel).split("/").map(enc).join("/");
  return "/api/projects/" + enc(state.current) + "/file/" + segs;
}

let toastTimer = null;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 3500);
}

function openModal(html) {
  $("modalBox").innerHTML = html;
  $("modal").classList.remove("hidden");
}
function closeModal() {
  $("modal").classList.add("hidden");
  $("modalBox").innerHTML = "";
}

function previewModal(url, kind) {
  let inner;
  if (kind === "image") inner = '<img src="' + url + '">';
  else if (kind === "video") inner = '<video src="' + url + '" controls autoplay></video>';
  else if (kind === "audio") inner = '<audio src="' + url + '" controls autoplay></audio>';
  else inner = '<p class="muted">No inline preview.</p>';
  openModal(inner + '<div style="margin-top:12px"><a class="btn" href="' + url + '" download>Download / open</a> <button class="btn ghost" onclick="closeModal()">Close</button></div>');
}

/* ------------------------------------------------------------------ */
/* bootstrap + projects                                                */
/* ------------------------------------------------------------------ */
async function init() {
  state.bootstrap = await apiGet("/api/bootstrap");
  renderTools();
  bindStatic();
  pollRunning();
  await refreshProjects();
  if (state.projects.length && !state.current) await selectProject(state.projects[0].name);
}

function bindStatic() {
  $("newProjectBtn").addEventListener("click", newProjectModal);
  $("openFolderBtn").addEventListener("click", () => apiPost("/api/projects/" + enc(state.current) + "/open"));
  $("keysBtn").addEventListener("click", keysModal);
  $("labBtn").addEventListener("click", openLab);
  $("consoleClose").addEventListener("click", closeConsole);
  $("consoleStop").addEventListener("click", () => stopJob());
  $("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });
  document.querySelectorAll("#tabs .tab").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
  });
}

function renderTools() {
  const t = state.bootstrap.tools;
  const rows = [
    ["FFmpeg", t.ffmpeg], ["ffprobe", t.ffprobe], ["yt-dlp", t.ytdlp],
    ["edge-tts", t.edge_tts], ["requests", t.requests],
    ["Chatterbox", t.chatterbox], ["Pocket TTS", t.pocket],
    ["ElevenLabs keys", t.keys.ELEVENLABS_API_KEY], ["MiniMax keys", t.keys.MINIMAX_API_KEY], ["Hugging Face token", t.keys.HF_TOKEN],
  ];
  $("toolsStatus").innerHTML =
    '<div class="row muted" style="font-weight:700;padding-bottom:4px">Tools</div>' +
    rows.map(([n, v]) =>
      '<div class="row"><span class="' + (v ? "ok" : "bad") + '">●</span> ' + n +
      (typeof v === "number" ? " (" + v + ")" : "") + "</div>").join("");
}

async function refreshProjects() {
  state.projects = await apiGet("/api/projects");
  renderProjectList();
}

function renderProjectList() {
  const list = $("projectList");
  if (!state.projects.length) {
    list.innerHTML = '<div class="muted" style="padding:8px">No projects yet.</div>';
    return;
  }
  list.innerHTML = state.projects.map((p) => {
    const modLabel = (state.bootstrap.modules.find(m => m[0] === p.module) || [p.module, p.module])[1];
    return '<div class="project-item ' + (p.name === state.current ? "active" : "") + '" data-name="' + esc(p.name) + '">' +
      '<div class="pname">' + esc(p.name) + '</div>' +
      '<div class="pmeta">' + esc(modLabel) + ' · ' + p.segments + ' seg</div>' +
    '</div>';
  }).join("");
  list.querySelectorAll(".project-item").forEach((el) => {
    el.addEventListener("click", () => selectProject(el.dataset.name));
  });
}

async function selectProject(name) {
  state.current = name;
  state.tab = "dashboard";
  await loadDetail();
  renderProjectList();
  switchTab("dashboard");
}

async function loadDetail() {
  if (!state.current) return;
  const d = await apiGet("/api/projects/" + enc(state.current));
  if (d.error) { toast(d.error); return; }
  state.detail = d;
  const seg = await apiGet("/api/projects/" + enc(state.current) + "/segments");
  state.segments = (seg && !seg.error) ? seg : { youtube: [], tiktok: {} };
  $("emptyState").classList.add("hidden");
  $("labView").classList.add("hidden");
  $("projectView").classList.remove("hidden");
  renderHeader();
}

function renderHeader() {
  const d = state.detail;
  $("projTitle").textContent = d.name;
  if ($("tabFootage")) $("tabFootage").textContent = isComic() ? "Comic" : "Footage";
  if ($("tabScenes")) {
    const show = state.detail.project.module === "movie_recap" || state.detail.project.module === "show_recap";
    $("tabScenes").style.display = show ? "" : "none";
    if (!show && state.tab === "scenes") state.tab = "dashboard";
  }
  const p = d.project;
  const modLabel = (state.bootstrap.modules.find(m => m[0] === p.module) || [p.module, p.module])[1];
  $("projMeta").innerHTML =
    '<span class="badge">' + esc(modLabel) + '</span>' +
    (p.topic ? '<span class="badge">' + esc(p.topic) + '</span>' : "") +
    (p.target_length ? '<span class="badge">' + esc(p.target_length) + '</span>' : "") +
    '<span class="badge">' + d.segment_counts.youtube + ' segments</span>' +
    (d.segment_counts.tiktok ? '<span class="badge">' + d.segment_counts.tiktok + ' tiktok</span>' : "") +
    (d.engine_current ? "" : '<span class="badge amber">engine outdated</span>');
}

function switchTab(tab) {
  state.tab = tab;
  if (tab === "scenes") state.scenes = null;
  document.querySelectorAll("#tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  renderTab();
}

function renderTab() {
  const c = $("tabContent");
  if (!state.detail) return;
  if (state.tab === "dashboard") renderDashboard(c);
  else if (state.tab === "pipeline") renderPipeline(c);
  else if (state.tab === "script") renderScript(c);
  else if (state.tab === "scenes") renderScenes(c);
  else if (state.tab === "footage") (isComic() ? renderComic(c) : renderFootage(c));
  else if (state.tab === "characters") renderCharacters(c);
  else if (state.tab === "voice") renderVoice(c);
  else if (state.tab === "outputs") renderOutputs(c);
  else if (state.tab === "settings") renderSettings(c);
}

/* ------------------------------------------------------------------ */
/* console + jobs                                                      */
/* ------------------------------------------------------------------ */
function fmtDur(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), r = sec % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(r).padStart(2, "0");
}

// progress bar + "12/40 · label · 1:20 elapsed · ~2:30 left"
function renderProgress(j) {
  const wrap = $("consoleProgress"), fill = $("pbarFill"), info = $("pinfo");
  const running = j.status === "running";
  wrap.classList.remove("hidden");
  const pr = j.progress;
  const elapsed = j.elapsed != null ? j.elapsed : (Date.now() / 1000 - j.started);
  let text = fmtDur(elapsed) + " elapsed";
  if (pr && pr.total > 0) {
    const frac = Math.min(1, pr.done / pr.total);
    fill.classList.remove("indeterminate");
    fill.style.width = (running ? frac * 100 : (j.status === "done" ? 100 : frac * 100)) + "%";
    text = pr.done + " / " + pr.total + " (" + Math.round(frac * 100) + "%)" +
      (pr.label ? " · " + pr.label : "") + " · " + text;
    if (running && pr.done > 0 && frac < 1) text += " · ~" + fmtDur(elapsed / pr.done * (pr.total - pr.done)) + " left";
  } else if (running) {
    fill.classList.add("indeterminate");
    text = "working… (this step has no exact progress) · " + text;
  } else {
    fill.classList.remove("indeterminate");
    fill.style.width = j.status === "done" ? "100%" : "0";
  }
  info.textContent = text;
}

function appendLog(j) {
  const logEl = $("consoleLog");
  const lines = j.log || [];
  if (lines.length < shownLines) { logEl.textContent = ""; shownLines = 0; }
  if (lines.length > shownLines) {
    const frag = document.createDocumentFragment();
    for (let i = shownLines; i < lines.length; i++) frag.appendChild(document.createTextNode(lines[i] + "\n"));
    logEl.appendChild(frag);
    shownLines = lines.length;
    logEl.scrollTop = logEl.scrollHeight;
  }
}

function openConsole(title) {
  $("consoleTitle").textContent = title;
  $("consoleStatus").textContent = "running…";
  $("consoleStatus").className = "console-status";
  $("consoleLog").textContent = "";
  $("consoleProgress").classList.add("hidden");
  $("consoleStop").classList.remove("hidden");
  $("consoleStop").disabled = false;
  $("consoleStop").textContent = "■ Stop";
  shownLines = 0;
  $("consoleWrap").classList.remove("hidden");
}
function closeConsole() {
  $("consoleWrap").classList.add("hidden");
}
function setConsoleStatus(status) {
  const el = $("consoleStatus");
  el.className = "console-status " + status;
  el.textContent = status === "done" ? "done ✓" : status === "error" ? "failed ✗"
    : status === "stopped" ? "stopped ■" : "running…";
  if (status !== "running") $("consoleStop").classList.add("hidden");
}

async function stopJob(jid) {
  jid = jid || activeJobId();
  if (!jid) return;
  if (!confirm("Stop this step now?\n\nWork already finished is kept; run the step again to continue (voice-over only redoes what's missing).")) return;
  const btn = $("consoleStop");
  btn.disabled = true; btn.textContent = "Stopping…";
  const r = await apiPost("/api/jobs/" + jid + "/stop");
  if (r.error) toast(r.error);
  pollRunning();
}

function activeJobId() { return activeJob || currentJobId; }

// reopen the console on a job that is already running (e.g. from the "Running now" box)
async function attachJob(jid, project) {
  if (project && project !== state.current) await selectProject(project);
  const j = await apiGet("/api/jobs/" + jid);
  if (!j || j.error) return;
  activeJob = jid;
  openConsole(j.label || j.step);
  pollJob();
}

async function startJob(step, flags, label) {
  if (!state.current) return;
  const res = await apiPost("/api/projects/" + enc(state.current) + "/run", { step, flags });
  if (res.error) {
    if (res.job) { toast("Something is already running on this project - showing it."); attachJob(res.job); }
    else toast(res.error);
    return;
  }
  activeJob = res.job;
  openConsole(label || step);
  pollJob();
}

let currentJobId = null;

async function pollJob() {
  if (!activeJob) return;
  const jid = activeJob;
  currentJobId = jid;
  const j = await apiGet("/api/jobs/" + jid);
  if (!j || j.error) return;
  if (activeJob !== jid) return;
  appendLog(j);
  renderProgress(j);
  if (j.status === "running") {
    setConsoleStatus("running");
    setTimeout(pollJob, 450);
  } else {
    setConsoleStatus(j.status);
    activeJob = null;
    pollRunning();
    await refreshAfterJob();
  }
}

/* ---- "Running now" box in the sidebar: what is running, on which project, with Stop ---- */
let runningTimer = null;
async function pollRunning() {
  clearTimeout(runningTimer);
  let data;
  try { data = await apiGet("/api/jobs"); } catch (e) { data = null; }
  const box = $("runningBox");
  const run = data && data.jobs ? data.jobs.filter((j) => j.status === "running") : [];
  if (!run.length) {
    box.classList.add("hidden");
  } else {
    box.classList.remove("hidden");
    box.innerHTML = '<div class="rtitle"><span class="dot-run"></span>Running now</div>' + run.map((j) => {
      const pr = j.progress;
      const pct = pr && pr.total ? Math.round(pr.done / pr.total * 100) : null;
      return '<div class="rjob" onclick="attachJob(\'' + j.id + '\',\'' + esc(j.project).replace(/\\/g, "\\\\").replace(/'/g, "\\'") + '\')">' +
        '<div class="rname"><b>' + esc(j.label || j.step) + '</b>' +
        '<button class="btn danger small" onclick="event.stopPropagation();stopJob(\'' + j.id + '\')">■ Stop</button></div>' +
        '<div class="rsub">' + esc(j.project) + ' · ' + fmtDur(j.elapsed) +
          (pr && pr.label ? ' · ' + esc(pr.label) : "") + '</div>' +
        '<div class="pbar"><div class="pbar-fill' + (pct == null ? " indeterminate" : "") + '" style="width:' + (pct == null ? 35 : pct) + '%"></div></div>' +
        '</div>';
    }).join("");
  }
  runningTimer = setTimeout(pollRunning, run.length ? 1500 : 4000);
}

async function refreshAfterJob() {
  state.scenes = null;
  await refreshProjects();
  await loadDetail();
  if (state.tab === "footage" && !isComic()) await loadMissing();
  renderTab();
}

/* ------------------------------------------------------------------ */
/* dashboard                                                           */
/* ------------------------------------------------------------------ */
function renderDashboard(c) {
  const d = state.detail, p = d.project;
  const modLabel = (state.bootstrap.modules.find(m => m[0] === p.module) || [p.module, p.module])[1];
  const out = d.outputs;
  const outBadges = [
    ["Final video", out.video], ["Premiere XML", out.premiere], ["VideoPad project", out.videopad], ["Subtitles", out.srt],
    ["Chapters", out.chapters], ["Shot list", out.shot_manifest], ["Credits", out.credits],
  ].map(([n, ok]) => '<span class="badge ' + (ok ? "good" : "") + '">' + n + (ok ? " ✓" : "") + "</span>").join("");

  c.innerHTML =
    '<div class="grid cols2">' +
      '<div class="card">' +
        '<h3 style="margin-top:0">Project</h3>' +
        '<div class="badges" style="margin-bottom:10px">' +
          '<span class="badge">' + esc(modLabel) + '</span>' +
          (p.topic ? '<span class="badge">' + esc(p.topic) + '</span>' : "") +
          '<span class="badge">' + esc(p.platform) + '</span>' +
          '<span class="badge">tts: ' + esc(p.tts_mode) + '</span>' +
        '</div>' +
        '<div class="muted" style="font-size:13px;line-height:1.6">' +
          '<div>Target length: <b>' + esc(p.target_length || "module default") + '</b></div>' +
          '<div>Segments: <b>' + d.segment_counts.youtube + '</b> youtube' +
            (d.segment_counts.tiktok ? ' · <b>' + d.segment_counts.tiktok + '</b> tiktok' : "") + '</div>' +
          '<div>Style: <b>' + esc(p.style || "—") + '</b> · Music bed: <b>' + (p.music ? "on" : "off") + '</b> · Captions: <b>' + (p.captions ? "on" : "off") + '</b></div>' +
        '</div>' +
        '<div style="margin-top:12px"><button class="btn" onclick="switchTab(\'settings\')">Edit settings</button> ' +
        '<button class="btn ghost" onclick="switchTab(\'script\')">Open script</button></div>' +
      '</div>' +
      '<div class="card">' +
        '<h3 style="margin-top:0">Outputs</h3>' +
        '<div class="badges">' + outBadges + '</div>' +
        '<div style="margin-top:12px"><button class="btn" onclick="switchTab(\'outputs\')">View outputs</button></div>' +
      '</div>' +
    '</div>' +
    (d.state ? '<div class="section" style="margin-top:20px"><h3>Status / next steps</h3><pre class="state">' + esc(d.state) + '</pre></div>' : "");
}

/* ------------------------------------------------------------------ */
/* pipeline (run steps)                                                */
/* ------------------------------------------------------------------ */
function isRecap() {
  const m = state.detail.project.module;
  return m === "movie_recap" || m === "show_recap" || m === "comic_recap";
}
function isComic() {
  return state.detail && state.detail.project.module === "comic_recap";
}

function pipelineSteps() {
  const engine = (state.detail.config.tts && state.detail.config.tts.engine) || "edge";
  const steps = [];
  if (isComic()) steps.push({ step: "comic", name: "Import comic / manga", desc: "Unpack the .cbz / .cbr / .pdf into pages, find the panels, and write the numbered PDF(s) for Claude into comic_review/. Tick Force to re-detect every panel." });
  else if (isRecap()) steps.push({ step: "subs", name: "Extract subtitles", desc: state.detail.project.module === "show_recap"
    ? "Pull the subtitles out of EVERY episode in footage/ in one run. Also makes subs/ALL_EPISODES_for_claude.txt - the one file to give Claude."
    : "Pull embedded subtitle tracks from the film into subs/." });
  else steps.push({ step: "index", name: "Index footage", desc: "Contact sheets for every clip in footage/." });
  if (!isComic()) steps.push({ step: "sheets", name: "Contact sheets", desc: "Sheets for segments marked need_visual." });
  steps.push({ step: "characters", name: "Check characters", desc: "List the PNG cut-outs in characters/, flag any without transparency, and make characters/_preview.png (corner + solo look)." });
  steps.push({ step: "review", name: "Export review sheet", desc: "Write review_sheet.csv (optional Excel workflow)." });
  steps.push({ step: "tts", name: "Voice-over", desc: "Generate narration audio (only new / edited segments).", engine });
  steps.push({ step: "premiere", name: "Build Premiere XML", desc: "Cut clips + multi-track XML (+ srt, chapters, shot list). Characters get their own video track." });
  steps.push({ step: "videopad", name: "Build VideoPad project", desc: "Same timeline as a VideoPad .vpj (V1 footage, character + graphics tracks, A1-A3). Click Try Load when VideoPad warns." });
  steps.push({ step: "videopad_simple", name: "Build VideoPad project (simple)", desc: "Fallback: picture + voice only, one file per segment (characters are baked into the picture). Use if the full project will not open." });
  steps.push({ step: "srt", name: "Build subtitles", desc: "Write recap_subtitles.srt for Premiere." });
  if (isRecap()) {
    steps.push({ step: "video", name: "Build full video", desc: isComic() ? "Camera moves (zoom / pan / swipe) rendered over the panels into one recap_final.mp4." : "One finished recap_final.mp4." });
    steps.push({ step: "tiktok", name: "Build TikTok", desc: "Vertical 9:16 parts into tiktok_out/." });
    if (!isComic()) {
      steps.push({ step: "timeline", name: "Build timeline.json", desc: "Write the timeline the Remotion renderer reads (needs voice-over first). Also works out the caption word timings." });
      steps.push({ step: "remotion", name: "Render with Remotion", desc: "Render recap_remotion.mp4 with Remotion (needs Node.js from SETUP.bat): word-by-word captions, chapter cards, lower thirds and transitions burned in. Change the look in config.json (captions / transitions / overlays)." });
      steps.push({ step: "scenes", name: "Check scenes", desc: "Custom Remotion scenes (scenes/<segment id>.tsx): safety check + test render of every changed scene. A scene that fails is replaced by the keywords scene and a SCENE_FIX_PROMPT.txt for Claude is written. Needs the timeline first." });
      steps.push({ step: "preview", name: "Preview scenes", desc: "Open Remotion Studio to look at one scene at a time (16:9 and 9:16). Needs the timeline first." });
      steps.push({ step: "scenes_demo", name: "Demo scenes", desc: "Test only, in a demo project: installs 3 good and 3 deliberately broken scenes so you can see the checks work. Then run Build timeline.json." });
    }
  }
  steps.push({ step: "check", name: "Status check", desc: "Report + rewrite STATE.md." });
  steps.push({ step: "demo", name: "Demo / test media", desc: "Fill with synthetic media (use a fresh project)." });
  return steps;
}

function runStep(step) {
  const s = pipelineSteps().find(x => x.step === step);
  const flags = {};
  if ($("forceChk") && $("forceChk").checked) flags.force = true;
  if (step === "tts") flags.engine = s.engine;
  if (step === "videopad_simple") { flags.simple = true; step = "videopad"; }
  if (step === "scenes_demo") { flags.demo = true; step = "scenes"; }
  startJob(step, flags, s.name);
}

function runPreview() {
  const s = pipelineSteps().find(x => x.step === "tts");
  startJob("tts", { engine: s.engine, preview: true }, "Preview voice (3 segments)");
}

function runAll() {
  const seq = isComic() ? ["comic", "tts", "premiere", "srt"]
            : isRecap() ? ["subs", "sheets", "tts", "premiere", "srt"]
                        : ["index", "sheets", "tts", "premiere", "srt"];
  runSequence(seq);
}

async function runSequence(steps) {
  openConsole("Run all");
  for (const step of steps) {
    const s = pipelineSteps().find(x => x.step === step);
    const flags = { engine: (state.detail.config.tts && state.detail.config.tts.engine) || "edge" };
    const res = await apiPost("/api/projects/" + enc(state.current) + "/run", { step, flags });
    if (res.error) { toast(res.error); closeConsole(); return; }
    activeJob = res.job;
    currentJobId = res.job;
    $("consoleTitle").textContent = "Run all → " + s.name;
    $("consoleStop").classList.remove("hidden");
    $("consoleStop").disabled = false;
    $("consoleStop").textContent = "■ Stop";
    $("consoleLog").textContent = ""; shownLines = 0;
    let j = { status: "running" };
    while (j && j.status === "running") {
      await new Promise(r => setTimeout(r, 500));
      j = await apiGet("/api/jobs/" + res.job);
      if (!j || j.error) break;
      appendLog(j);
      renderProgress(j);
    }
    setConsoleStatus(j.status);
    if (j.status !== "done") { toast(j.status === "stopped" ? "Stopped at: " + s.name : "Stopped at step: " + s.name); break; }
  }
  activeJob = null;
  pollRunning();
  await refreshAfterJob();
}

function renderPipeline(c) {
  const steps = pipelineSteps();
  c.innerHTML =
    '<div class="section">' +
      '<div style="display:flex;align-items:center;gap:16px;margin-bottom:14px;flex-wrap:wrap">' +
        '<button class="btn primary" onclick="runAll()">▶ Run all</button>' +
        '<label class="check" style="margin:0"><input type="checkbox" id="forceChk"> Force redo (overwrite outputs)</label>' +
      '</div>' +
      '<div class="step-grid">' +
        steps.map((s) => {
          let actions;
          if (s.step === "tts") {
            actions = '<button class="btn primary small" onclick="runStep(\'tts\')">Generate</button>' +
                      '<button class="btn small" onclick="runPreview()">Preview</button>';
          } else if (s.step === "video") {
            actions = '<button class="btn primary small" onclick="runStep(\'video\')">Build</button>';
          } else if (s.step === "premiere" || s.step === "videopad") {
            actions = '<button class="btn primary small" onclick="runStep(\'' + s.step + '\')">Build</button>';
          } else {
            actions = '<button class="btn small" onclick="runStep(\'' + s.step + '\')">Run</button>';
          }
          return '<div class="step">' +
            '<div class="sname">' + esc(s.name) + '</div>' +
            '<div class="sdesc">' + esc(s.desc) + '</div>' +
            '<div class="row">' + actions + '</div>' +
          '</div>';
        }).join("") +
      '</div>' +
    '</div>' +
    '<p class="muted">For guided footage collection and drag-and-drop uploads, use the <b>Footage</b> tab.</p>';
}

/* ------------------------------------------------------------------ */
/* script (segments editor)                                            */
/* ------------------------------------------------------------------ */
function segField(label, f, value, textarea) {
  value = value == null ? "" : value;
  return '<div><label>' + esc(label) + '</label>' +
    (textarea
      ? '<textarea data-f="' + f + '">' + esc(value) + '</textarea>'
      : '<input data-f="' + f + '" value="' + esc(value) + '">') +
    '</div>';
}

function segSelect(label, f, value, options) {
  value = value == null ? "" : String(value);
  const opts = options.slice();
  if (value && !opts.some((o) => (Array.isArray(o) ? o[0] : o) === value)) opts.push(value);
  return '<div><label>' + esc(label) + '</label><select data-f="' + f + '">' +
    opts.map((o) => {
      const v = Array.isArray(o) ? o[0] : o, t = Array.isArray(o) ? o[1] : o;
      return '<option value="' + esc(v) + '"' + (v === value ? " selected" : "") + '>' + esc(t) + '</option>';
    }).join("") + '</select></div>';
}

const CHAR_POSITIONS = [["", "(default)"], "bottom-right", "bottom-left", "bottom-center", "center", "middle", "left", "right", "top-left", "top-right"];

// a segment's character wishes as flat fields (the script may hold them nested: "character": {"name": ..., "pos": ...})
function segCharFields(seg) {
  const out = {};
  const c = seg.character;
  if (c === false) out.character = "__none";
  else if (c && typeof c === "object") {
    if (c.name) out.character = c.name;
    ["pos", "pose", "scale", "anim", "enter", "exit", "flip", "layout", "bg", "outline", "shadow", "x", "y"].forEach((k) => {
      if (c[k] != null && c[k] !== "") out["char_" + k] = c[k];
    });
  } else if (typeof c === "string") out.character = c;
  ["pos", "pose", "scale", "anim", "enter", "exit", "flip", "layout", "bg", "outline", "shadow", "x", "y"].forEach((k) => {
    if (seg["char_" + k] != null && seg["char_" + k] !== "") out["char_" + k] = seg["char_" + k];
  });
  return out;
}

function segCharacterBox(seg) {
  const cf = segCharFields(seg);
  const names = ((state.detail && state.detail.characters) || []).map((c) => c.name);
  const used = Object.keys(cf).length > 0 || seg.commentary;
  return '<details class="charbox"' + (used ? " open" : "") + '><summary>🧍 Character' +
      (cf.character && cf.character !== "__none" ? ": " + esc(cf.character) : "") + '</summary>' +
    '<div class="mini-grid">' +
      segSelect("character", "character", cf.character || "", [["", "(project default / none)"], ["__none", "(no character here)"]].concat(names)) +
      segSelect("layout", "char_layout", cf.char_layout || "", [["", "auto"], ["corner", "corner (over the clip)"], ["solo", "solo (on a background)"]]) +
      segSelect("position", "char_pos", cf.char_pos || "", CHAR_POSITIONS) +
      segField("pose", "char_pose", cf.char_pose) +
      segSelect("animation", "char_anim", cf.char_anim || "", [["", "(default: talk)"], "talk", "breathe", "bob", "float", "sway", "shake", "none", "talk+sway", "talk+bob"]) +
      segSelect("enter", "char_enter", cf.char_enter || "", [["", "(default)"], "slide", "pop", "fade", "none"]) +
      segField("solo background", "char_bg", cf.char_bg) +
      segField("size (0.1-1.2)", "char_scale", cf.char_scale) +
    '</div>' +
    '<label class="check"><input type="checkbox" data-f="commentary"' + (seg.commentary ? " checked" : "") + '> commentary beat (solo scene if there is no footage)</label>' +
  '</details>';
}

function renderSegmentCard(seg, part) {
  const shot = seg.shot || {};
  const est = wordsToSec(seg.narration);
  return '<div class="seg" data-part="' + part + '" data-id="' + esc(seg.id || "") + '">' +
    '<div class="seg-head">' +
      '<span class="seg-id">' + esc(seg.id || "(new)") + '</span>' +
      '<span class="seg-est">~' + est + 's voice</span>' +
      '<button class="btn danger small" onclick="removeSeg(this)">Remove</button>' +
    '</div>' +
    '<label>Narration</label>' +
    '<textarea class="narration" data-f="narration">' + esc(seg.narration) + '</textarea>' +
    '<div class="mini-grid">' +
      segField("src_start", "src_start", seg.src_start) +
      segField("src_end", "src_end", seg.src_end) +
      segField("src (file)", "src", seg.src) +
      segField("image (file)", "image", seg.image) +
      segField("subtitle", "subtitle", seg.subtitle) +
      segField("caption", "caption", seg.caption) +
      segField("rank", "rank", seg.rank) +
      segField("chapter", "chapter", seg.chapter) +
    '</div>' +
    '<div class="mini-grid">' +
      segField("Shot description", "shot.description", shot.description) +
      segField("Shot queries (one per line)", "shot.queries", (shot.queries || []).join("\n"), true) +
      segField("Shot fallback", "shot.fallback", shot.fallback) +
    '</div>' +
    segCharacterBox(seg) +
    '<label class="check"><input type="checkbox" data-f="keep_audio"' + (seg.keep_audio ? " checked" : "") + '> keep original audio</label>' +
    '<label class="check"><input type="checkbox" data-f="need_visual"' + (seg.need_visual ? " checked" : "") + '> need contact sheet</label>' +
  '</div>';
}

function removeSeg(btn) {
  btn.closest(".seg").remove();
}

function readSegCard(card) {
  const get = (f) => { const el = card.querySelector('[data-f="' + f + '"]'); return el ? el.value : ""; };
  const checked = (f) => { const el = card.querySelector('[data-f="' + f + '"]'); return el ? el.checked : false; };
  const seg = { id: card.dataset.id || "" };
  const set = (k, v) => { if (v !== "" && v !== false) seg[k] = v; };
  set("narration", get("narration"));
  set("src_start", get("src_start"));
  set("src_end", get("src_end"));
  set("src", get("src"));
  set("image", get("image"));
  set("subtitle", get("subtitle"));
  set("caption", get("caption"));
  set("rank", get("rank"));
  set("chapter", get("chapter"));
  if (checked("keep_audio")) seg.keep_audio = true;
  if (checked("commentary")) seg.commentary = true;
  const ch = get("character");
  if (ch === "__none") seg.character = false;
  else if (ch) seg.character = ch;
  ["layout", "pos", "pose", "anim", "enter", "bg", "scale"].forEach((k) => {
    const v = get("char_" + k);
    if (v !== "") seg["char_" + k] = (k === "scale" && !isNaN(parseFloat(v))) ? parseFloat(v) : v;
  });
  if (checked("need_visual")) seg.need_visual = true;
  const sd = get("shot.description"), sq = get("shot.queries"), sf = get("shot.fallback");
  if (sd || sq || sf) {
    seg.shot = {};
    if (sd) seg.shot.description = sd;
    if (sf) seg.shot.fallback = sf;
    if (sq) seg.shot.queries = sq.split("\n").map(s => s.trim()).filter(Boolean);
  }
  return seg;
}

function collectSegmentsFromDOM() {
  const youtube = [], tiktok = {};
  document.querySelectorAll(".seg").forEach((card) => {
    const part = card.dataset.part;
    const seg = readSegCard(card);
    if (!seg.id) return;
    if (part === "youtube") youtube.push(seg);
    else {
      const p = part.replace("tiktok:", "");
      (tiktok[p] = tiktok[p] || []).push(seg);
    }
  });
  return { youtube, tiktok };
}

async function saveScript() {
  const seg = collectSegmentsFromDOM();
  const res = await apiPost("/api/projects/" + enc(state.current) + "/segments", { segments: seg });
  if (res.error) { toast(res.error); return; }
  toast("Script saved ✓");
  await loadDetail();
}

function addSegment() {
  const n = document.querySelectorAll('.seg[data-part="youtube"]').length + 1;
  const id = "yt_" + String(n).padStart(3, "0");
  const div = document.createElement("div");
  div.innerHTML = renderSegmentCard({ id, narration: "" }, "youtube");
  document.getElementById("segmentsWrap").appendChild(div.firstElementChild);
  div.firstElementChild.scrollIntoView({ behavior: "smooth" });
}

async function importPaste() {
  const text = document.getElementById("pasteText").value;
  if (!text.trim()) { toast("Paste Claude's reply first."); return; }
  const res = await apiPost("/api/projects/" + enc(state.current) + "/paste", { text });
  if (res.error) { toast(res.error); return; }
  toast("Imported: " + res.youtube + " segments" + (res.tiktok ? ", " + res.tiktok + " tiktok" : "") +
    (res.motion ? " · " + res.motion + " motion brief(s)" : ""));
  await loadDetail();
  renderTab();
  scriptCheckModal(res);
}

// plain-language problems found in the pasted script (motion briefs, transitions, theme): shown once, copyable for Claude
function scriptCheckModal(res) {
  const errs = res.errors || [], warns = res.warnings || [], tm = res.theme_messages || [];
  if (!errs.length && !warns.length && !tm.length) return;
  const asText = errs.concat(warns).map((m) => "- " + m).join("\n");
  window._scriptIssues = "Please fix these problems in the JSON you sent and send the whole corrected JSON again:\n" + asText;
  openModal(
    '<h2>Script check</h2>' +
    (errs.length ? '<p><b>Needs fixing</b> (the pipeline ignores or mishandles these):</p><ul>' + errs.map((m) => '<li>' + esc(m) + '</li>').join("") + '</ul>' : "") +
    (warns.length ? '<p><b>Advice</b>:</p><ul>' + warns.map((m) => '<li>' + esc(m) + '</li>').join("") + '</ul>' : "") +
    (tm.length ? '<p><b>Theme</b>:</p><ul>' + tm.map((m) => '<li>' + esc(m) + '</li>').join("") + '</ul>' : "") +
    '<div style="display:flex;gap:8px;margin-top:14px">' +
      ((errs.length || warns.length) ? '<button class="btn small" onclick="navigator.clipboard.writeText(window._scriptIssues).then(()=>toast(\'Copied: paste it to Claude\'))">Copy as a message to Claude</button>' : "") +
      '<button class="btn small primary" onclick="closeModal()">OK</button></div>');
}

function copyPrompt() {
  navigator.clipboard.writeText(document.getElementById("promptText").textContent)
    .then(() => toast("Prompt copied ✓"), () => toast("Copy failed"));
}

function toggleRaw() {
  document.getElementById("rawWrap").classList.toggle("hidden");
}

async function saveRaw() {
  try {
    const obj = JSON.parse(document.getElementById("rawJson").value);
    const res = await apiPost("/api/projects/" + enc(state.current) + "/segments", { segments: obj });
    if (res.error) { toast(res.error); return; }
    toast("Raw JSON saved ✓");
    await loadDetail();
    renderTab();
  } catch (e) { toast("Invalid JSON: " + e.message); }
}

function renderScript(c) {
  const d = state.detail;
  const yt = state.segments.youtube || [];
  const tt = state.segments.tiktok || {};
  const parts = Object.keys(tt).map((p) =>
    '<div class="section"><h3>TikTok · ' + esc(p) + '</h3>' +
    (tt[p] || []).map((s) => renderSegmentCard(s, "tiktok:" + p)).join("") + '</div>').join("");

  c.innerHTML =
    '<div class="section">' +
      '<h3>Claude prompt</h3>' +
      '<div class="card">' +
        (d.prompt
          ? '<div style="max-height:160px;overflow:auto" class="mono" id="promptText">' + esc(d.prompt) + '</div>' +
            '<button class="btn small" style="margin-top:8px" onclick="copyPrompt()">Copy prompt</button>'
          : '<p class="muted">No PASTE_THIS_TO_CLAUDE.txt in this project yet.</p>') +
      '</div>' +
    '</div>' +
    '<div class="section">' +
      '<h3>Paste Claude\'s reply</h3>' +
      '<div class="card">' +
        '<textarea id="pasteText" style="min-height:90px" placeholder="Paste Claude\'s whole answer here (the JSON is extracted automatically)…"></textarea>' +
        '<button class="btn primary" style="margin-top:8px" onclick="importPaste()">Import JSON</button>' +
      '</div>' +
    '</div>' +
    '<div class="section">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">' +
        '<h3 style="margin:0">Segments (' + yt.length + ')</h3>' +
        '<div><button class="btn small" onclick="addSegment()">＋ Add segment</button> ' +
        '<button class="btn small ghost" onclick="toggleRaw()">Raw JSON</button></div>' +
      '</div>' +
      '<div id="segmentsWrap">' + yt.map((s) => renderSegmentCard(s, "youtube")).join("") + '</div>' +
      parts +
      '<div class="card hidden" id="rawWrap" style="margin-top:12px">' +
        '<label>Raw segments.json</label>' +
        '<textarea id="rawJson" style="min-height:200px;font-family:monospace">' + esc(JSON.stringify(state.segments, null, 2)) + '</textarea>' +
        '<button class="btn small" style="margin-top:8px" onclick="saveRaw()">Save raw JSON</button>' +
      '</div>' +
      '<div style="margin-top:12px"><button class="btn primary" onclick="saveScript()">💾 Save script</button></div>' +
    '</div>';
}

/* ------------------------------------------------------------------ */
/* scenes (Phase 3): Claude-written motion scenes                      */
/* ------------------------------------------------------------------ */
const SCENE_STATE = {
  ok: ["passed", "good"], ready: ["written, not checked", "amber"], missing: ["not written yet", "amber"],
  stale: ["brief changed", "amber"], failed: ["failed: fallback used", "bad"], blocked: ["blocked: fallback used", "bad"],
  unchecked: ["not checked", "amber"], pending: ["not written yet", "amber"], fallback: ["keywords scene (your choice)", ""],
};

async function loadScenes() {
  const r = await apiGet("/api/projects/" + enc(state.current) + "/scenes");
  state.scenes = r && !r.error ? r : { rows: [], error: r && r.error };
}

function sceneUrl(rel) { return "/api/projects/" + enc(state.current) + "/file/" + rel.split("/").map(enc).join("/"); }

function renderScenes(c) {
  if (!state.scenes) {
    c.innerHTML = '<p class="muted">Loading scenes…</p>';
    if (!state.scenesLoading) {
      state.scenesLoading = true;
      loadScenes().then(() => { state.scenesLoading = false; if (state.tab === "scenes") renderTab(); });
    }
    return;
  }
  const sc = state.scenes, rows = sc.rows || [];
  const todo = rows.filter((r) => r.state === "missing" || r.state === "stale" || r.state === "failed" || r.state === "blocked").length;
  const okN = rows.filter((r) => r.state === "ok").length;
  const table = rows.length ? rows.map((r) => {
    const st = SCENE_STATE[r.state] || [r.state, ""];
    const thumbs = (r.frames || []).slice(0, 3).map((f) => '<a href="' + sceneUrl(f) + '" target="_blank" rel="noopener"><img src="' + sceneUrl(f) + '" style="height:54px;border-radius:4px;margin-right:4px"></a>').join("");
    const btns = [];
    if (r.state === "failed" || r.state === "blocked" || r.state === "unchecked" || r.state === "ready" || r.state === "stale") btns.push('<button class="btn small" onclick="sceneAction(\'' + esc(r.id) + '\',\'retry\')">Check again</button>');
    if (r.state === "fallback") btns.push('<button class="btn small" onclick="sceneAction(\'' + esc(r.id) + '\',\'unfallback\')">Use the scene</button>');
    else btns.push('<button class="btn small ghost" onclick="sceneAction(\'' + esc(r.id) + '\',\'fallback\')">Use keywords instead</button>');
    if (r.exists) btns.push('<button class="btn small ghost" title="Move the scene file away so the next prompt writes it again" onclick="sceneAction(\'' + esc(r.id) + '\',\'discard\')">Write again</button>');
    return '<div class="card" style="margin-bottom:8px">' +
      '<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><div><b>' + esc(r.id) + '</b> ' +
        '<span class="badge ' + st[1] + '">' + esc(st[0]) + '</span> ' +
        (r.cost ? '<span class="badge">cost ' + esc(r.cost) + '</span> ' : "") +
        (r.seconds ? '<span class="badge">' + r.seconds + ' s</span>' : "") + '</div>' +
        '<div class="badges">' + btns.join(" ") + '</div></div>' +
      '<div style="margin:6px 0">' + esc(r.brief) + '</div>' +
      (r.message ? '<div class="muted" style="font-size:12px">' + esc(r.message) + '</div>' : "") +
      (r.warnings && r.warnings.length ? '<div class="muted" style="font-size:12px">note: ' + esc(r.warnings.join(" · ")) + '</div>' : "") +
      (thumbs ? '<div style="margin-top:6px">' + thumbs + '</div>' : "") + '</div>';
  }).join("") : '<div class="card"><p class="muted" style="margin:0">No segment has a <code>motion</code> brief yet. Ask Claude for the script with the movie prompt (it now includes a graphics section) and paste it on the Script tab, or add three test briefs with the button below.</p></div>';

  c.innerHTML =
    '<div class="section"><h3>How custom scenes work</h3><div class="card">' +
      '<ol style="margin:0;padding-left:18px;line-height:1.7">' +
        '<li><b>Script</b> (Script tab): Claude adds a short <code>motion</code> brief to the segments that deserve a designed graphic, and a <code>theme</code> for the film.</li>' +
        '<li><b>Scenes</b> (here): copy the scene prompt, paste it to Claude, paste Claude\'s reply back. The scenes are saved, safety-checked and test-rendered.</li>' +
        '<li>A scene that fails is replaced by the keywords scene, so the video never stops. Copy the fix prompt for Claude, paste the answer back, check again.</li>' +
      '</ol>' +
      '<p class="muted" style="margin:10px 0 0">Theme: ' + (sc.has_theme ? '<b>' + esc(sc.theme || "unnamed") + '</b> (theme.json)' : 'none yet (default look)') +
        (sc.has_proposed_theme ? ' · Claude proposed another theme: see theme.proposed.json (your theme.json was kept)' : '') +
        ' · Custom scenes appear in the Remotion render only (Premiere / VideoPad / ffmpeg exports show their normal placeholder).</p>' +
    '</div></div>' +

    '<div class="section"><h3>Step 2 · Scene prompt</h3><div class="card">' +
      '<p style="margin-top:0">' + rows.length + ' brief(s) · ' + okN + ' passed · ' + todo + ' to write or fix.</p>' +
      '<label style="display:flex;gap:6px;align-items:center;margin-bottom:8px"><input type="checkbox" id="scForce" style="width:auto"> Also rewrite scenes that are already done</label>' +
      '<button class="btn primary" onclick="copyScenePrompt()">Copy scene prompt for Claude</button> ' +
      (sc.has_fix_prompt ? '<button class="btn" onclick="copyFixPrompt()">Copy fix prompt (failed scenes)</button> ' : "") +
      '<div id="scPromptShow"></div>' +
    '</div></div>' +

    '<div class="section"><h3>Paste Claude\'s reply</h3><div class="card">' +
      '<textarea id="scReply" style="min-height:90px" placeholder="Paste Claude\'s whole answer here: every code block that starts with // FILE: scenes/<id>.tsx is saved (also works for the fix prompt answer)…"></textarea>' +
      '<button class="btn primary" style="margin-top:8px" onclick="importScenes()">Import scenes and check them</button>' +
      (sc.has_timeline ? "" : '<p class="muted" style="margin:8px 0 0">There is no timeline.json yet, so scenes can only be saved now; run <b>Build timeline.json</b> (Run steps) to check them.</p>') +
    '</div></div>' +

    '<div class="section"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><h3 style="margin:0">Scenes (' + rows.length + ')</h3>' +
      '<div class="badges"><button class="btn small" onclick="startJob(\'scenes\', {}, \'Check scenes\')">Check scenes</button> ' +
      '<button class="btn small" onclick="startJob(\'preview\', {}, \'Preview scenes\')">Open in Remotion Studio</button> ' +
      '<button class="btn small ghost" onclick="demoBriefs()">Add demo briefs (test)</button></div></div>' +
      table + '</div>';
}

async function copyToClipboardOrShow(text, label) {
  try { await navigator.clipboard.writeText(text); toast(label + " copied ✓ (" + Math.round(text.length / 1000) + " KB)"); return; } catch (e) { /* fall through */ }
  const box = $("scPromptShow");
  if (box) box.innerHTML = '<p class="muted">The browser blocked copying. Select all and copy:</p><textarea readonly style="min-height:140px;font-family:monospace" onclick="this.select()">' + esc(text) + '</textarea>';
}

async function copyScenePrompt() {
  const force = !!($("scForce") && $("scForce").checked);
  const r = await apiPost("/api/projects/" + enc(state.current) + "/scenes/prompt", { force });
  if (r.error) { toast(r.error); return; }
  if (!r.count) {
    toast(r.skipped && r.skipped.length ? "Nothing to write: all " + r.skipped.length + " scene(s) are done. Tick 'Also rewrite' to redo them." : "No segment has a motion brief yet.");
    return;
  }
  await copyToClipboardOrShow(r.text, "Scene prompt for " + r.count + " scene(s)");
}

async function copyFixPrompt() {
  const r = await apiGet("/api/projects/" + enc(state.current) + "/scenes/fixprompt");
  if (!r || !r.text) { toast("There is no fix prompt: no scene failed."); return; }
  await copyToClipboardOrShow(r.text, "Fix prompt");
}

async function importScenes() {
  const text = $("scReply").value;
  if (!text.trim()) { toast("Paste Claude's reply first."); return; }
  const r = await apiPost("/api/projects/" + enc(state.current) + "/scenes/import", { text });
  if (r.error) { toast(r.error); return; }
  const n = (r.imported || []).length;
  const notes = (r.skipped || []).map((x) => x[0] + ": " + x[1]).concat(r.warnings || []);
  state.scenes = null;
  if (!n) {
    openModal('<h2>Nothing imported</h2><ul>' + notes.map((m) => '<li>' + esc(m) + '</li>').join("") + '</ul><button class="btn small primary" onclick="closeModal()">OK</button>');
    renderTab();
    return;
  }
  toast("Saved " + n + " scene(s): " + r.imported.join(", "));
  if (notes.length) openModal('<h2>Imported ' + n + ' scene(s)</h2><ul>' + notes.map((m) => '<li>' + esc(m) + '</li>').join("") + '</ul><button class="btn small primary" onclick="closeModal()">OK</button>');
  if (r.has_timeline) startJob("scenes", {}, "Check scenes"); else renderTab();
}

async function sceneAction(id, what) {
  const r = await apiPost("/api/projects/" + enc(state.current) + "/scenes/action", { id, what });
  if (r.error) { toast(r.error); return; }
  toast(r.message || "done");
  state.scenes = null;
  if (what === "retry") { startJob("scenes", {}, "Check scenes"); return; }
  renderTab();
}

async function demoBriefs() {
  const r = await apiPost("/api/projects/" + enc(state.current) + "/scenes/demo", {});
  if (r.error) { toast(r.error); return; }
  toast(r.message);
  await loadDetail();
  state.scenes = null;
  renderTab();
}

/* ------------------------------------------------------------------ */
/* footage (collect + upload)                                          */
/* ------------------------------------------------------------------ */
async function loadMissing() {
  const m = await apiGet("/api/projects/" + enc(state.current) + "/missing");
  state.missing = Array.isArray(m) ? m : [];
  if (m && m.error) state.missing = [{ id: "error", missing: true, why: m.error }];
}

function searchLinks(queries) {
  const kinds = [
    "https://www.youtube.com/results?search_query=",
    "https://x.com/search?f=video&q=",
    "https://www.google.com/search?tbm=isch&q=",
  ];
  return (queries || []).slice(0, 3).map((q, i) =>
    '<a href="' + kinds[i] + encodeURIComponent(q) + '" target="_blank" rel="noopener">' + esc(q) + '</a>').join("");
}

async function uploadFile(folder, file, id) {
  folder = folder || "footage";
  const url = "/api/projects/" + enc(state.current) + "/upload?folder=" + enc(folder) +
    "&name=" + enc(file.name) + (id ? "&id=" + enc(id) : "");
  const r = await fetch(url, { method: "POST", body: file });
  const j = await r.json();
  if (j.error) { toast(j.error); return; }
  if (id) {
    toast(j.ok ? "Attached to shot ✓" : "Attach failed");
    await loadMissing();
  } else {
    toast("Uploaded ✓");
    await loadDetail();
  }
  renderTab();
}

function uploadFileInput(input, folder, id) {
  const files = Array.from(input.files || []);
  input.value = "";
  if (!files.length) return;
  if (files.length === 1 || id) uploadFile(folder, files[0], id);
  else uploadMany(folder, files);
}

// several files at once (e.g. all episodes of a season): sent one after another, with progress
async function uploadMany(folder, files) {
  files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  let ok = 0;
  for (let i = 0; i < files.length; i++) {
    toast("Uploading " + (i + 1) + " of " + files.length + ": " + files[i].name + " …");
    try {
      const url = "/api/projects/" + enc(state.current) + "/upload?folder=" + enc(folder) +
        "&name=" + enc(files[i].name);
      const j = await (await fetch(url, { method: "POST", body: files[i] })).json();
      if (j.error) { toast(files[i].name + ": " + j.error); continue; }
      ok++;
    } catch (e) { toast("Upload failed: " + files[i].name); }
  }
  toast("Uploaded " + ok + " of " + files.length + " ✓");
  await loadDetail();
  renderTab();
}

async function downloadShot(id) {
  const urlEl = document.querySelector('[data-shot-url="' + id + '"]');
  const rngEl = document.querySelector('[data-shot-range="' + id + '"]');
  const url = urlEl ? urlEl.value.trim() : "";
  if (!url) { toast("Paste a URL first."); return; }
  const res = await apiPost("/api/projects/" + enc(state.current) + "/download",
    { id, url, range: rngEl ? rngEl.value.trim() : "" });
  if (res.error) { toast(res.error); return; }
  activeJob = res.job;
  openConsole("Download " + id);
  pollJob();
}

async function skipShot(id) {
  const res = await apiPost("/api/projects/" + enc(state.current) + "/skip", { id });
  if (res.error) { toast(res.error); return; }
  activeJob = res.job;
  openConsole("Skip " + id);
  pollJob();
}

function mediaItem(name, kind, url) {
  let inner;
  if (kind === "image") inner = '<img class="thumb" src="' + url + '" loading="lazy">';
  else if (kind === "video") inner = '<div class="thumb" style="display:grid;place-items:center">🎞️</div>';
  else if (kind === "audio") inner = '<div class="thumb" style="display:grid;place-items:center">🎵</div>';
  else inner = '<div class="thumb" style="display:grid;place-items:center">📄</div>';
  return '<div class="media-item" onclick="previewModal(\'' + url + '\',\'' + kind + '\')">' + inner +
    '<div class="mname" title="' + esc(name) + '">' + esc(name) + '</div></div>';
}

function episodesSection(d) {
  const eps = (d.files.footage || []).filter((f) => f.kind === "video");
  return '<div class="section"><h3>Episodes</h3>' +
    '<div class="card">' +
      '<p class="muted" style="margin-top:0">Select <b>all the episodes at once</b> (Ctrl+A in the file picker). ' +
      'They are saved in footage/. For a whole season, <b>📂 Open folder</b> and drag them into <code>footage</code> is faster. ' +
      'Then go to <b>Run steps → Extract subtitles</b>: it does every episode in one go.</p>' +
      '<label class="btn primary small" style="display:inline-block">⬆ Upload episodes (many at once)' +
        '<input type="file" multiple accept="video/*,.mkv,.ts,.m2ts" style="display:none" onchange="uploadFileInput(this,\'footage\')"></label>' +
      '<div class="muted" style="margin-top:10px"><b>' + eps.length + '</b> episode file(s) in footage/' +
        (eps.length ? ': ' + eps.map((f) => esc(f.name)).join(", ") : "") + '</div>' +
    '</div></div>';
}

function folderSection(title, folder, files, allowUpload) {
  const items = (files || []).map((f) =>
    mediaItem(f.name, f.kind, fileUrl(folder + "/" + f.name))).join("");
  return '<div class="section"><h3>' + title + '</h3>' +
    (allowUpload ? '<label class="btn small" style="margin-bottom:8px;display:inline-block">⬆ Upload ' +
      '<input type="file" multiple style="display:none" onchange="uploadFileInput(this,\'' + folder + '\')"></label>' : "") +
    '<div class="media-grid">' + (items || '<div class="muted">empty</div>') + '</div></div>';
}

let comicShown = 24;
async function renderComic(c) {
  const d = state.detail;
  let meta = null;
  try {
    const r = await fetch(fileUrl("pages/panels.json") + "?t=" + Date.now());
    if (r.ok) meta = await r.json();
  } catch (e) { meta = null; }
  const pages = (meta && meta.pages) || [];
  const npan = pages.reduce((a, p) => a + (p.panels || []).length, 0);
  const comicFiles = (d.root_media || []).filter((f) => /\.(cbz|cbr|cb7|zip|rar|7z|pdf|epub)$/i.test(f.name));
  const review = (d.files.comic_review || []);
  const pdfs = review.filter((f) => /\.pdf$/i.test(f.name));
  const imgs = review.filter((f) => f.kind === "image");
  const shown = imgs.slice(0, comicShown);
  c.innerHTML =
    '<div class="section"><h3>1 · The comic file</h3><div class="card">' +
      '<p class="muted" style="margin-top:0">Upload a <b>.cbz</b>, <b>.cbr</b> or <b>.pdf</b> (or a .zip of page images). ' +
      'You can also just drop the file into the project folder. Then run <b>Import comic / manga</b>.</p>' +
      '<label class="btn small" style="margin-bottom:8px;display:inline-block">⬆ Upload comic' +
        '<input type="file" accept=".cbz,.cbr,.cb7,.zip,.rar,.7z,.pdf,.epub" style="display:none" onchange="uploadFileInput(this,\'root\')"></label> ' +
      '<button class="btn primary small" onclick="runStep(\'comic\')">▶ Import comic / manga</button> ' +
      '<button class="btn ghost small" onclick="apiPost(\'/api/projects/' + enc(state.current) + '/open\')">📂 Open folder</button>' +
      '<div class="media-grid" style="margin-top:8px">' +
        (comicFiles.map((f) => mediaItem(f.name, f.kind, fileUrl(f.name))).join("") || '<div class="muted">no comic file in the project folder yet</div>') +
      '</div></div></div>' +
    '<div class="section"><h3>2 · Imported: ' + pages.length + ' page(s), ' + npan + ' panel(s) ' +
      (meta ? '<span class="badge">' + (meta.reading === "rtl" ? "right-to-left" : "left-to-right") + '</span>' : "") + '</h3>' +
      (pdfs.length
        ? '<div class="card"><p class="muted" style="margin-top:0">Give <b>one PDF per message</b> to Claude together with the prompt (Script tab → prompt). ' +
          'Panel numbers in these PDFs are what <code>segments.json</code> points at.</p>' +
          pdfs.map((f) => '<a class="btn small" style="margin:0 6px 6px 0" href="' + fileUrl("comic_review/" + f.name) + '" download>⬇ ' + esc(f.name) + ' (' + (f.size / 1e6).toFixed(1) + ' MB)</a>').join("") + '</div>'
        : '<div class="card muted">Nothing imported yet.</div>') +
      (shown.length
        ? '<div class="media-grid" style="margin-top:10px">' + shown.map((f) => mediaItem(f.name, f.kind, fileUrl("comic_review/" + f.name))).join("") + '</div>' +
          (imgs.length > shown.length ? '<p><button class="btn small" onclick="comicShown+=48;renderTab()">Show more (' + (imgs.length - shown.length) + ' left)</button></p>' : "") +
          '<p class="muted">Wrong split on a page? Edit <code>pages/panels.json</code> (pixel boxes, reading order) and run the import again <i>without</i> Force.</p>'
        : "") +
    '</div>' +
    folderSection("Music", "music", d.files.music, true);
}

async function renderFootage(c) {
  await loadMissing();
  const d = state.detail;
  const missing = state.missing.filter((m) => m.missing);
  const shotHtml = missing.length
    ? missing.map((m) => {
        const st = m.status === "skipped" ? '<span class="badge amber">skipped</span>'
                 : m.status === "done" ? '<span class="badge good">done</span>' : "";
        return '<div class="shot">' +
          '<div class="seg-head"><span class="seg-id">' + esc(m.id) + '</span>' + st + '</div>' +
          (m.description ? '<div class="desc">' + esc(m.description) + '</div>' : "") +
          (m.narration ? '<div class="muted">' + esc(m.narration) + '</div>' : "") +
          (m.queries && m.queries.length ? '<div class="queries">' + searchLinks(m.queries) + '</div>' : "") +
          (m.fallback ? '<div class="muted">Fallback: ' + esc(m.fallback) + '</div>' : "") +
          '<div class="row" style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">' +
            '<input data-shot-url="' + esc(m.id) + '" placeholder="https://…  (with optional range)" style="flex:1;min-width:200px">' +
            '<input data-shot-range="' + esc(m.id) + '" placeholder="1:42-1:51" style="width:110px">' +
            '<button class="btn primary small" onclick="downloadShot(\'' + esc(m.id) + '\')">Download</button>' +
            '<button class="btn small" onclick="skipShot(\'' + esc(m.id) + '\')">Skip</button>' +
            '<label class="btn small" style="margin:0">📎 Attach file<input type="file" style="display:none" onchange="uploadFileInput(this,null,\'' + esc(m.id) + '\')"></label>' +
          '</div>' +
        '</div>';
      }).join("")
    : '<div class="card">All segments have footage. 🎉</div>';

  c.innerHTML =
    '<div class="section"><h3>Missing shots (' + missing.length + ')</h3>' + shotHtml + '</div>' +
    (d.project.module === "show_recap" ? episodesSection(d) : "") +
    folderSection("Footage", "footage", d.files.footage, true) +
    folderSection("Images", "images", d.files.images, true) +
    folderSection("Music", "music", d.files.music, true) +
    '<div class="section"><h3>' + (isRecap() ? "The film / episode (project root)" : "Project root media") + '</h3>' +
      (isRecap() ? '<p class="muted">Recaps: put the film here. "Extract subtitles" and single-film recaps look in this folder, ' +
        'not in Footage. Several episodes: see the Show recap guide.</p>' : "") +
      '<label class="btn small" style="margin-bottom:8px;display:inline-block">⬆ Upload video' +
        '<input type="file" multiple accept="video/*,.mkv,.ts,.m2ts" style="display:none" onchange="uploadFileInput(this,\'root\')"></label>' +
      '<div class="media-grid">' + ((d.root_media || []).map((f) => mediaItem(f.name, f.kind, fileUrl(f.name))).join("") ||
        '<div class="muted">empty</div>') + '</div></div>';
}

/* ------------------------------------------------------------------ */
/* characters (PNG cut-outs that appear on screen in commentary moments) */
/* ------------------------------------------------------------------ */
function charCard(ch) {
  const def = (ch.poses.find((p) => p.pose === "default") || ch.poses[0]);
  const poses = ch.poses.map((p) =>
    '<span class="chip" title="Click to preview" onclick="previewModal(\'' + fileUrl(p.file) + '\',\'image\')">' + esc(p.pose) +
    ' <a href="#" title="Delete this pose" onclick="event.stopPropagation();charDelete(\'' + esc(ch.name) + '\',\'' + esc(p.pose) + '\');return false">×</a></span>').join("");
  return '<div class="charcard">' +
    '<div class="cutout"><img src="' + fileUrl(def.file) + '?t=' + Date.now() + '" loading="lazy"></div>' +
    '<div class="cname">' + esc(ch.name) + '</div>' +
    '<div class="chips">' + poses + '</div>' +
    '<label>Art faces</label>' +
    '<select onchange="charFacing(\'' + esc(ch.name) + '\',this.value)">' +
      [["", "not set"], ["left", "left"], ["right", "right"]].map((o) =>
        '<option value="' + o[0] + '"' + ((ch.facing || "") === o[0] ? " selected" : "") + '>' + o[1] + '</option>').join("") +
    '</select>' +
    '<div class="row" style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">' +
      '<label class="btn small" style="margin:0">＋ Pose<input type="file" accept="image/png,image/webp" multiple style="display:none" onchange="charAddPoses(this,\'' + esc(ch.name) + '\')"></label>' +
      '<button class="btn danger small" onclick="charDelete(\'' + esc(ch.name) + '\')">Delete</button>' +
    '</div>' +
  '</div>';
}

function renderCharacters(c) {
  const d = state.detail, chars = d.characters || [];
  const pc = d.project.character || {}, cc = (d.config && d.config.character) || {};
  const dc = (state.bootstrap.default_config && state.bootstrap.default_config.character) || {};
  const v = (k) => (cc[k] != null ? cc[k] : dc[k]);
  const sel = (id, val, opts) => '<select id="' + id + '">' + opts.map((o) => {
    const ov = Array.isArray(o) ? o[0] : o, ot = Array.isArray(o) ? o[1] : o;
    return '<option value="' + esc(ov) + '"' + (String(val) === String(ov) ? " selected" : "") + '>' + esc(ot) + '</option>';
  }).join("") + '</select>';
  const hasPreview = ((d.files.characters || []).some((f) => f.name === "_preview.png"));
  c.innerHTML =
    '<div class="section"><h3>Character animation</h3>' +
      '<div class="card"><p class="muted" style="margin-top:0">Add <b>transparent PNG cut-outs</b> of your characters. In the script, give a segment a ' +
      '<code>character</code> and it appears on its own video layer: in a <b>corner over movie / show / doc clips</b>, or ' +
      '<b>centered on a background</b> for solo commentary. The mouth pose (<code>talk</code>) opens and closes with the voice-over. ' +
      'In Premiere and VideoPad the character is a separate track you can still move, scale or delete. ' +
      'Mp4 and TikTok builds have it baked in.</p>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:end">' +
        '<div style="min-width:200px"><label style="margin-top:0">Character name</label><input id="chNewName" placeholder="e.g. kratos"></div>' +
        '<label class="btn primary small" style="margin:0">⬆ Add PNG(s)<input type="file" accept="image/png,image/webp" multiple style="display:none" onchange="charAdd(this)"></label>' +
        '<button class="btn small" onclick="runStep(\'characters\')">Check + make preview</button>' +
        '<button class="btn ghost small" onclick="apiPost(\'/api/projects/' + enc(state.current) + '/open\')">📂 Open folder</button>' +
      '</div>' +
      '<p class="muted" style="margin-bottom:0">One file = one picture. Several files = poses named after the files (<code>default.png</code>, <code>talk.png</code> = mouth open, <code>angry.png</code> …). ' +
      'Poses can also be dropped in <code>characters/&lt;name&gt;/</code>, or named <code>name__pose.png</code>.</p></div></div>' +
    '<div class="section"><h3>Library (' + chars.length + ')</h3>' +
      (chars.length ? '<div class="char-grid">' + chars.map(charCard).join("") + '</div>'
                    : '<div class="card muted">No characters yet. Add a transparent PNG above.</div>') + '</div>' +
    (hasPreview ? '<div class="section"><h3>Preview</h3><div class="card"><img style="max-width:100%;border-radius:8px" src="' +
      fileUrl("characters/_preview.png") + '?t=' + Date.now() + '"><p class="muted" style="margin-bottom:0">Left: corner over footage. Right: solo scene.</p></div></div>' : "") +
    '<div class="section"><h3>Defaults for this project</h3><div class="card">' +
      '<div class="grid cols2">' +
        '<div><label style="margin-top:0">Default character</label>' +
          sel("chDefault", pc.default || "", [["", "(none)"]].concat(chars.map((x) => x.name))) +
        '<label>Show it automatically on</label>' +
          sel("chAuto", pc.auto || "off", [["off", "only segments that name a character"], ["commentary", "segments marked commentary: true"], ["all", "every segment"]]) +
        '<label>Corner position</label>' + sel("chPos", v("corner_pos"), CHAR_POSITIONS.slice(1)) +
        '<label>Size over clips (share of frame height)</label><input id="chScale" value="' + esc(v("corner_scale")) + '">' +
        '<label>Size in solo scenes</label><input id="chSolo" value="' + esc(v("solo_scale")) + '"></div>' +
        '<div><label style="margin-top:0">Idle animation</label>' +
          sel("chIdle", v("idle"), ["talk", "breathe", "bob", "float", "sway", "shake", "none", "talk+sway", "talk+bob"]) +
        '<label>Enter / exit over clips</label>' + sel("chEnter", v("enter"), ["slide", "pop", "fade", "none"]) +
        '<label>Solo background (#hex, gradient:#a,#b, or an image / video file name)</label><input id="chBg" value="' + esc(v("solo_bg")) + '">' +
        '<label>Layer file format</label>' + sel("chCodec", v("codec"), [["qtrle", "qtrle - works everywhere (big files)"], ["png", "png - about half the size"], ["prores", "prores 4444 - smallest (not for VideoPad)"]]) +
        '<label class="check"><input type="checkbox" id="chShadow"' + (v("shadow") !== false ? " checked" : "") + '> soft drop shadow</label>' +
        '<label class="check"><input type="checkbox" id="chOutline"' + (v("outline") ? " checked" : "") + '> white sticker outline</label></div>' +
      '</div>' +
      '<button class="btn primary" style="margin-top:12px" onclick="saveCharacterSettings()">Save</button>' +
    '</div></div>';
}

async function saveCharacterSettings() {
  const num = (id, dflt) => { const x = parseFloat($(id).value); return isNaN(x) ? dflt : x; };
  const proj = await apiPost("/api/projects/" + enc(state.current) + "/settings",
    { project: { character: { default: $("chDefault").value, auto: $("chAuto").value } } });
  const cfg = await apiPost("/api/projects/" + enc(state.current) + "/config", { config: { character: {
    corner_pos: $("chPos").value, corner_scale: num("chScale", 0.46), solo_scale: num("chSolo", 0.8),
    idle: $("chIdle").value, enter: $("chEnter").value, exit: $("chEnter").value,
    solo_bg: $("chBg").value.trim() || "gradient:#1b2030,#43305f", codec: $("chCodec").value,
    shadow: $("chShadow").checked, outline: $("chOutline").checked ? "#ffffff" : "" } } });
  if (proj.error || cfg.error) { toast(proj.error || cfg.error); return; }
  toast("Character settings saved ✓");
  await loadDetail();
  renderTab();
}

async function uploadCharFile(sub, fname, file) {
  const url = "/api/projects/" + enc(state.current) + "/upload?folder=characters&sub=" + enc(sub) + "&name=" + enc(fname);
  const j = await (await fetch(url, { method: "POST", body: file })).json();
  if (j.error) { toast(fname + ": " + j.error); return false; }
  return true;
}

async function charAdd(input) {
  const files = Array.from(input.files || []);
  input.value = "";
  if (!files.length) return;
  const base = (f) => f.name.replace(/\.[^.]+$/, "");
  let name = ($("chNewName").value || "").trim();
  if (!name) {
    if (files.length > 1) { toast("Type the character's name first (several files = poses of one character)."); return; }
    name = base(files[0]);
  }
  let ok = 0;
  for (const f of files) {
    const ext = (f.name.match(/\.[^.]+$/) || [".png"])[0].toLowerCase();
    const pose = files.length === 1 ? "default" : base(f).toLowerCase().replace(/\s+/g, "_");
    if (await uploadCharFile(name, pose + ext, f)) ok++;
  }
  toast("Added " + ok + " file(s) to " + name + " ✓");
  await loadDetail();
  renderTab();
}

async function charAddPoses(input, name) {
  const files = Array.from(input.files || []);
  input.value = "";
  let ok = 0;
  for (const f of files) {
    const ext = (f.name.match(/\.[^.]+$/) || [".png"])[0].toLowerCase();
    if (await uploadCharFile(name, f.name.replace(/\.[^.]+$/, "").toLowerCase().replace(/\s+/g, "_") + ext, f)) ok++;
  }
  toast("Added " + ok + " pose(s) ✓");
  await loadDetail();
  renderTab();
}

async function charDelete(name, pose) {
  if (!confirm(pose ? "Delete pose '" + pose + "' of " + name + "?" : "Delete the character '" + name + "' and all its poses?")) return;
  const r = await apiPost("/api/projects/" + enc(state.current) + "/character", { action: "delete", name, pose: pose || "" });
  if (r.error) { toast(r.error); return; }
  await loadDetail();
  renderTab();
}

async function charFacing(name, facing) {
  const r = await apiPost("/api/projects/" + enc(state.current) + "/character", { action: "facing", name, facing });
  if (r.error) { toast(r.error); return; }
  await loadDetail();
}

/* ------------------------------------------------------------------ */
/* voice                                                               */
/* ------------------------------------------------------------------ */
function renderVoice(c) {
  const cfg = state.detail.config || {};
  const t = cfg.tts || {};
  const engine = t.engine || "edge";
  const engOpts = state.bootstrap.engines.map(e =>
    '<option value="' + e[0] + '"' + (e[0] === engine ? " selected" : "") + '>' + esc(e[1]) + '</option>').join("");
  const edgeOpts = state.bootstrap.edge_voices.map(v =>
    '<option value="' + v[0] + '"' + (v[0] === t.edge_voice ? " selected" : "") + '>' + esc(v[1]) + '</option>').join("");
  const kkOpts = state.bootstrap.kokoro_voices.map(v =>
    '<option value="' + v[0] + '"' + (v[0] === (t.kokoro_voice || "am_michael") ? " selected" : "") + '>' + esc(v[1]) + '</option>').join("");
  const mmOpts = state.bootstrap.minimax_voices.map(v =>
    '<option value="' + v[0] + '"' + (v[0] === t.minimax_voice ? " selected" : "") + '>' + esc(v[1]) + '</option>').join("");

  c.innerHTML =
    '<div class="grid cols2">' +
      '<div class="card">' +
        '<h3 style="margin-top:0">Voice settings</h3>' +
        '<label>Engine</label><select id="vEngine" onchange="voiceEngineChange()">' + engOpts + '</select>' +
        ttsControlsHTML("v", t, engine) +
        '<button class="btn primary" style="margin-top:14px" onclick="saveVoiceConfig()">Save voice settings</button>' +
      '</div>' +
      '<div class="card">' +
        '<h3 style="margin-top:0">Generate</h3>' +
        '<p class="muted">Preview voices 3 segments before spending credits; generate only re-voices new/edited text.</p>' +
        '<div class="row" style="display:flex;gap:8px;flex-wrap:wrap">' +
          '<button class="btn" onclick="runVoice(false)">🎙 Generate (changed only)</button>' +
          '<button class="btn" onclick="hearSegments()">▶ Preview 3 segments (plays here)</button>' +
          '<button class="btn danger" onclick="runVoice(false, true)">Regenerate all</button>' +
        '</div>' +
        '<div class="muted" style="margin-top:12px">' +
          (state.bootstrap.tools.keys.ELEVENLABS_API_KEY
            ? 'ElevenLabs keys: ' + state.bootstrap.tools.keys.ELEVENLABS_API_KEY + ' · '
            : "") +
          (state.bootstrap.tools.keys.MINIMAX_API_KEY
            ? 'MiniMax keys: ' + state.bootstrap.tools.keys.MINIMAX_API_KEY : "") +
          (state.bootstrap.tools.edge_tts ? "" : '<span class="bad">edge-tts missing (run SETUP.bat)</span>') +
          ' <button class="btn small" onclick="keysModal()">🔑 Manage API keys</button>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div class="card" style="margin-top:16px"><h3 style="margin-top:0">🎧 Hear it here</h3>' +
      '<p class="muted">Plays in the browser with the settings on the left, even before you save them. ElevenLabs / MiniMax use credits.</p>' +
      '<textarea id="vHearText" rows="3" placeholder="Type something to hear…">' + esc(((((state.segments && state.segments.youtube) || [])[0] || {}).narration || "").slice(0, 400)) + '</textarea>' +
      '<div style="margin-top:8px"><button class="btn primary" onclick="hearHere()">▶ Play this text</button> <span id="vHearStatus" class="muted"></span></div>' +
      '<div id="vHearList"></div>' +
    '</div>';
}

function voiceEngineChange() { ttsEngineChange("v"); }

async function saveVoiceConfig() {
  const { tts } = readTts("v");
  const res = await apiPost("/api/projects/" + enc(state.current) + "/config", { config: { tts } });
  if (res.error) { toast(res.error); return; }
  toast("Voice settings saved ✓");
  await loadDetail();
}

async function fetchElevenLabsVoices(p) {
  p = p || "v";
  const res = await apiPost("/api/elevenlabs/voices", {});
  if (res.error) { toast(res.error); return; }
  const opts = res.voices.map(v => '<option value="' + esc(v.voice_id) + '">' + esc(v.name) + '</option>').join("");
  const el = document.getElementById(p + "ElVoice");
  const cur = el.value;
  el.outerHTML = '<select id="' + p + 'ElVoice">' + opts + '</select>';
  if (cur) document.getElementById(p + "ElVoice").value = cur;
  toast("Loaded " + res.voices.length + " voices");
}

/* ---- reference-voice field: type a name (autocomplete from voices/) or upload a clip ---- */
function voiceRefField(inputId, listId, value, names) {
  return '<div style="display:flex;gap:8px;align-items:center">' +
    '<input id="' + inputId + '" list="' + listId + '" value="' + esc(value) + '" placeholder="e.g. narrator  (file in voices/)">' +
    '<datalist id="' + listId + '">' + (names || []).map(n => '<option value="' + esc(n.replace(/\.[^.]+$/, "")) + '">').join("") + '</datalist>' +
    '<label class="btn small" style="margin:0;cursor:pointer">⬆ Upload clip<input type="file" accept="audio/*" style="display:none" ' +
      'onchange="uploadVoiceRef(this,\'' + inputId + '\',\'' + listId + '\')"></label>' +
  '</div>';
}

/* ---- Pocket TTS voice: a real dropdown (built-in voices + your clips + Custom) with Upload clip beside it ---- */
function pocketVoiceField(p, value, builtins, files) {
  const stem = n => n.replace(/\.[^.]+$/, "");
  const clips = (files || []).map(stem);
  const names = (builtins || []).map(v => v[0]);
  const known = names.includes(value) || clips.includes(value);
  const id = p + "PkVoice";
  return '<div style="display:flex;gap:8px;align-items:center">' +
      '<select id="' + id + 'Sel" onchange="pocketVoicePick(\'' + id + '\')">' +
        '<optgroup label="Built-in voices">' +
          (builtins || []).map(v => '<option value="' + esc(v[0]) + '"' + (v[0] === value ? " selected" : "") + '>' + esc(v[1] || v[0]) + '</option>').join("") +
        '</optgroup>' +
        '<optgroup label="My clips (voices folder)" id="' + id + 'Clips">' +
          clips.map(c => '<option value="' + esc(c) + '"' + (c === value ? " selected" : "") + '>' + esc(c) + '</option>').join("") +
        '</optgroup>' +
        '<option value="__custom__"' + (known ? "" : " selected") + '>Custom… (file path or hf:// link)</option>' +
      '</select>' +
      '<label class="btn small" style="margin:0;cursor:pointer">⬆ Upload clip<input type="file" accept="audio/*" style="display:none" ' +
        'onchange="uploadVoiceRef(this,\'' + id + '\',\'\')"></label>' +
    '</div>' +
    '<input id="' + id + '" value="' + esc(value) + '" placeholder="path to a clip, or hf://…" style="margin-top:8px' + (known ? ";display:none" : "") + '">';
}

function pocketVoicePick(id) {
  const sel = document.getElementById(id + "Sel"), inp = document.getElementById(id);
  if (sel.value === "__custom__") { inp.style.display = ""; inp.focus(); }
  else { inp.value = sel.value; inp.style.display = "none"; }
}

/* called after an uploaded clip is saved: add it to the Pocket dropdown and select it */
function voiceRefUploaded(inputId, stem) {
  const sel = document.getElementById(inputId + "Sel");
  if (!sel) return;
  if (!Array.from(sel.options).some(o => o.value === stem)) {
    const o = document.createElement("option");
    o.value = stem; o.textContent = stem;
    document.getElementById(inputId + "Clips").appendChild(o);
  }
  sel.value = stem;
  const inp = document.getElementById(inputId);
  inp.value = stem; inp.style.display = "none";
}

async function uploadVoiceRef(input, inputId, listId) {
  const f = input.files && input.files[0];
  if (!f) return;
  toast("Uploading " + f.name + "…");
  try {
    const r = await fetch("/api/voices/upload?name=" + encodeURIComponent(f.name), { method: "POST", body: f });
    const j = await r.json();
    if (j.error) { toast(j.error); return; }
    state.bootstrap.voice_files = j.voice_files || [];
    document.getElementById(inputId).value = j.file.replace(/\.[^.]+$/, "");
    const dl = document.getElementById(listId);
    if (dl) {
      const have = Array.from(dl.options).map(o => o.value);
      (j.voice_files || []).forEach(n => { const b = n.replace(/\.[^.]+$/, ""); if (!have.includes(b)) dl.insertAdjacentHTML("beforeend", '<option value="' + esc(b) + '">'); });
    }
    voiceRefUploaded(inputId, j.file.replace(/\.[^.]+$/, ""));
    toast("Saved to voices/" + j.file + " ✓" + (j.note ? " " + j.note : ""));
  } catch (e) { toast("Upload failed: " + e); }
  input.value = "";
}

function cbVariantChange(p) {
  const v = document.getElementById(p + "CbVariant").value;
  document.getElementById(p + "CbLangRow").classList.toggle("hidden", v !== "multilingual");
  document.getElementById(p + "CbEmoRow").classList.toggle("hidden", v === "turbo" || v === "nano");
}

/* ---- shared voice controls (project Voice tab + Voice Lab) ---- */
function ttsControlsHTML(p, t, engine) {
  const bs = state.bootstrap;
  const opts = (list, cur) => list.map(v => '<option value="' + v[0] + '"' + (v[0] === cur ? " selected" : "") + '>' + esc(v[1]) + '</option>').join("");
  const hid = (e) => (engine === e ? "" : "hidden");
  return (
    '<div id="' + p + 'Edge" class="' + hid("edge") + '">' +
      '<label>Edge voice</label><select id="' + p + 'EdgeVoice">' + opts(bs.edge_voices, t.edge_voice) + '</select>' +
      '<label>Rate</label><input id="' + p + 'EdgeRate" value="' + esc(t.edge_rate || "+0%") + '">' +
    '</div>' +
    '<div id="' + p + 'Kokoro" class="' + hid("kokoro") + '">' +
      '<label>Kokoro voice</label><select id="' + p + 'KokoroVoice">' + opts(bs.kokoro_voices, t.kokoro_voice || "am_michael") + '</select>' +
      '<label>Speed (1.0 = normal, 1.15 = faster)</label><input id="' + p + 'KokoroSpeed" value="' + esc(t.kokoro_speed != null ? t.kokoro_speed : 1.0) + '">' +
      '<label>Blend in a second voice (optional)</label><select id="' + p + 'KokoroVoice2"><option value="">none</option>' + opts(bs.kokoro_voices, t.kokoro_voice2 || "") + '</select>' +
      '<label>How much of voice 2, in % (0 = off, 30-50 = a new in-between voice)</label><input id="' + p + 'KokoroMix" value="' + esc(t.kokoro_mix != null ? t.kokoro_mix : 0) + '">' +
      '<label>Pause after a sentence / after a comma, in seconds (lower = more conversational)</label>' +
      '<div class="form-row"><div><input id="' + p + 'KokoroPS" value="' + esc(t.kokoro_sentence_pause != null ? t.kokoro_sentence_pause : 0.25) + '"></div>' +
      '<div><input id="' + p + 'KokoroPC" value="' + esc(t.kokoro_clause_pause != null ? t.kokoro_clause_pause : 0.1) + '"></div></div>' +
      '<p class="muted">Runs on your PC. The first run downloads the ~350 MB model once. No audio tags: they are stripped.' +
        (bs.tools.kokoro ? "" : ' <span class="bad">kokoro-onnx missing (run SETUP.bat)</span>') + '</p>' +
    '</div>' +
    '<div id="' + p + 'Chatter" class="' + hid("chatterbox") + '">' +
      '<label>Model</label><select id="' + p + 'CbVariant" onchange="cbVariantChange(\'' + p + '\')">' +
        opts(bs.chatterbox_variants, t.chatterbox_variant || "turbo") + '</select>' +
      '<div id="' + p + 'CbLangRow" class="' + ((t.chatterbox_variant || "turbo") === "multilingual" ? "" : "hidden") + '">' +
        '<label>Language</label><select id="' + p + 'CbLang">' + opts(bs.chatterbox_langs, t.chatterbox_language || "en") + '</select></div>' +
      '<label>Reference voice - clone any voice from a 5-15 s clip, best as .wav (blank = built-in voice)</label>' +
      voiceRefField(p + "CbVoice", p + "CbList", t.chatterbox_voice || "", bs.voice_files) +
      '<div id="' + p + 'CbEmoRow" class="form-row ' + (["turbo", "nano"].includes(t.chatterbox_variant || "turbo") ? "hidden" : "") + '">' +
        '<div><label>Exaggeration (0.25 flat · 0.5 normal · 1+ dramatic)</label><input id="' + p + 'CbExag" value="' + esc(t.chatterbox_exaggeration != null ? t.chatterbox_exaggeration : 0.5) + '"></div>' +
        '<div><label>Pacing / CFG (lower = slower, more deliberate)</label><input id="' + p + 'CbCfg" value="' + esc(t.chatterbox_cfg_weight != null ? t.chatterbox_cfg_weight : 0.5) + '"></div>' +
      '</div>' +
      '<div class="form-row3">' +
        '<div><label>Variation (temperature)</label><input id="' + p + 'CbTemp" value="' + esc(t.chatterbox_temperature != null ? t.chatterbox_temperature : 0.8) + '"></div>' +
        '<div><label>Speed</label><input id="' + p + 'CbSpeed" value="' + esc(t.chatterbox_speed != null ? t.chatterbox_speed : 1.0) + '"></div>' +
        '<div><label>Seed (0 = random)</label><input id="' + p + 'CbSeed" value="' + esc(t.chatterbox_seed != null ? t.chatterbox_seed : 0) + '"></div>' +
      '</div>' +
      '<div class="form-row"><div><label>Pause between sentences (s)</label><input id="' + p + 'CbPause" value="' + esc(t.chatterbox_sentence_pause != null ? t.chatterbox_sentence_pause : 0.25) + '"></div>' +
        '<div><label>Device</label><select id="' + p + 'CbDevice">' +
          ["auto", "cuda", "mps", "cpu"].map(d => '<option' + (((t.chatterbox_device || "auto") === d) ? " selected" : "") + '>' + d + '</option>').join("") +
        '</select></div></div>' +
      '<label class="chk"><input type="checkbox" id="' + p + 'CbNorm"' + (t.tts_normalize === false ? "" : " checked") + '> Level every clip to the same loudness</label>' +
      '<p class="muted">Runs on your PC (an NVIDIA GPU is strongly recommended). <b>Nano and Turbo</b> perform tags written in the script: ' +
        bs.chatterbox_tags.map(x => '<code>[' + x + ']</code>').join(" ") +
        ' (set the project voice style to light/heavy). <code>[pause]</code> works on every model. ' +
        'Output carries Resemble AI\'s inaudible Perth watermark.' +
        (bs.tools.chatterbox ? "" : ' <span class="bad">Not installed: run SETUP.bat and pick Chatterbox, then reload this page.</span>') + '</p>' +
    '</div>' +
    '<div id="' + p + 'Pocket" class="' + hid("pocket") + '">' +
      '<label>Voice - pick a built-in voice or one of your clips, or choose Custom to clone from a path / hf:// link</label>' +
      pocketVoiceField(p, t.pocket_voice || "alba", bs.pocket_voices, bs.voice_files) +
      '<div class="form-row3">' +
        '<div><label>Variation (temperature)</label><input id="' + p + 'PkTemp" value="' + esc(t.pocket_temperature != null ? t.pocket_temperature : 0.7) + '"></div>' +
        '<div><label>Quality steps (1 fast · 3-5 cleaner)</label><input id="' + p + 'PkSteps" value="' + esc(t.pocket_lsd_steps != null ? t.pocket_lsd_steps : 1) + '"></div>' +
        '<div><label>Speed</label><input id="' + p + 'PkSpeed" value="' + esc(t.pocket_speed != null ? t.pocket_speed : 1.0) + '"></div>' +
      '</div>' +
      '<div class="form-row"><div><label>Stop sensitivity (-4 default · higher ends sooner)</label><input id="' + p + 'PkEos" value="' + esc(t.pocket_eos_threshold != null ? t.pocket_eos_threshold : -4.0) + '"></div>' +
        '<div><label>Pause between sentences (s)</label><input id="' + p + 'PkPause" value="' + esc(t.pocket_sentence_pause != null ? t.pocket_sentence_pause : 0.25) + '"></div></div>' +
      '<label class="chk"><input type="checkbox" id="' + p + 'PkNorm"' + (t.tts_normalize === false ? "" : " checked") + '> Level every clip to the same loudness</label>' +
      '<p class="muted">Tiny 100M model that runs faster than real time on a normal CPU. English only, no emotion tags (they are stripped); ' +
        '<code>[pause]</code> works. Voice cloning needs only a short clean clip, best as a 16-bit <b>.wav</b> (Upload clip converts mp3/m4a/flac/ogg for you). If you see <i>soundfile is required</i>, see the guide: Clip format.' +
        (bs.tools.pocket ? "" : ' <span class="bad">Not installed: run SETUP.bat and pick Pocket TTS, then reload this page.</span>') + '</p>' +
    '</div>' +
    '<div id="' + p + 'Mini" class="' + hid("minimax") + '">' +
      '<label>MiniMax voice</label><select id="' + p + 'MiniVoice">' + opts(bs.minimax_voices, t.minimax_voice) + '</select>' +
    '</div>' +
    '<div id="' + p + 'Eleven" class="' + hid("elevenlabs") + '">' +
      '<label>ElevenLabs voice ID</label>' +
      '<div style="display:flex;gap:8px">' +
        '<input id="' + p + 'ElVoice" value="' + esc(t.elevenlabs_voice_id || "") + '" placeholder="voice id">' +
        '<button class="btn small" onclick="fetchElevenLabsVoices(\'' + p + '\')">Fetch</button>' +
      '</div>' +
      '<label>Model (eleven_v3 understands [tags])</label><input id="' + p + 'ElModel" value="' + esc(t.elevenlabs_model || "eleven_v3") + '">' +
      '<label>Stability</label><input id="' + p + 'ElStab" value="' + esc(t.elevenlabs_stability != null ? t.elevenlabs_stability : 0.5) + '">' +
    '</div>'
  );
}

function ttsEngineChange(p) {
  const e = document.getElementById(p + "Engine").value;
  document.getElementById(p + "Edge").classList.toggle("hidden", e !== "edge");
  document.getElementById(p + "Mini").classList.toggle("hidden", e !== "minimax");
  document.getElementById(p + "Kokoro").classList.toggle("hidden", e !== "kokoro");
  document.getElementById(p + "Chatter").classList.toggle("hidden", e !== "chatterbox");
  document.getElementById(p + "Pocket").classList.toggle("hidden", e !== "pocket");
  document.getElementById(p + "Eleven").classList.toggle("hidden", e !== "elevenlabs");
}

function readTts(p) {
  const g = (id) => document.getElementById(p + id).value;
  const engine = g("Engine");
  const tts = { engine };
  if (engine === "edge") {
    tts.edge_voice = g("EdgeVoice");
    tts.edge_rate = g("EdgeRate");
  } else if (engine === "kokoro") {
    tts.kokoro_voice = g("KokoroVoice");
    tts.kokoro_speed = parseFloat(g("KokoroSpeed")) || 1.0;
    tts.kokoro_voice2 = g("KokoroVoice2");
    tts.kokoro_mix = parseFloat(g("KokoroMix")) || 0;
    const ps = parseFloat(g("KokoroPS")), pc = parseFloat(g("KokoroPC"));
    tts.kokoro_sentence_pause = isNaN(ps) ? 0.25 : ps;
    tts.kokoro_clause_pause = isNaN(pc) ? 0.1 : pc;
  } else if (engine === "chatterbox") {
    const n = (id, d) => { const v = parseFloat(g(id)); return isNaN(v) ? d : v; };
    tts.chatterbox_variant = g("CbVariant");
    tts.chatterbox_language = g("CbLang");
    tts.chatterbox_voice = g("CbVoice").trim();
    tts.chatterbox_exaggeration = n("CbExag", 0.5);
    tts.chatterbox_cfg_weight = n("CbCfg", 0.5);
    tts.chatterbox_temperature = n("CbTemp", 0.8);
    tts.chatterbox_speed = n("CbSpeed", 1.0);
    tts.chatterbox_seed = Math.round(n("CbSeed", 0));
    tts.chatterbox_sentence_pause = n("CbPause", 0.25);
    tts.chatterbox_device = g("CbDevice");
    tts.tts_normalize = document.getElementById(p + "CbNorm").checked;
  } else if (engine === "pocket") {
    const n = (id, d) => { const v = parseFloat(g(id)); return isNaN(v) ? d : v; };
    tts.pocket_voice = g("PkVoice").trim() || "alba";
    tts.pocket_temperature = n("PkTemp", 0.7);
    tts.pocket_lsd_steps = Math.max(1, Math.round(n("PkSteps", 1)));
    tts.pocket_eos_threshold = n("PkEos", -4.0);
    tts.pocket_speed = n("PkSpeed", 1.0);
    tts.pocket_sentence_pause = n("PkPause", 0.25);
    tts.tts_normalize = document.getElementById(p + "PkNorm").checked;
  } else if (engine === "minimax") {
    tts.minimax_voice = g("MiniVoice");
  } else {
    tts.elevenlabs_voice_id = g("ElVoice").trim();
    tts.elevenlabs_model = g("ElModel").trim();
    tts.elevenlabs_stability = parseFloat(g("ElStab") || "0.5");
  }
  return { engine, tts };
}

function ttsLabel(engine, t) {
  if (engine === "edge") return "Edge · " + (t.edge_voice || "");
  if (engine === "kokoro") return "Kokoro · " + (t.kokoro_voice || "") + (t.kokoro_voice2 && t.kokoro_mix > 0 ? " + " + t.kokoro_voice2 + " " + t.kokoro_mix + "%" : "") + " · ×" + (t.kokoro_speed || 1);
  if (engine === "chatterbox") return "Chatterbox " + (t.chatterbox_variant || "turbo") + " · " + (t.chatterbox_voice || "built-in") + (t.chatterbox_speed && t.chatterbox_speed != 1 ? " · ×" + t.chatterbox_speed : "");
  if (engine === "pocket") return "Pocket TTS · " + (t.pocket_voice || "alba") + (t.pocket_speed && t.pocket_speed != 1 ? " · ×" + t.pocket_speed : "");
  if (engine === "minimax") return "MiniMax · " + (t.minimax_voice || "");
  return "ElevenLabs · " + (t.elevenlabs_voice_id || "") + " · " + (t.elevenlabs_model || "");
}

/* ---- speak text in the browser (used by Voice Lab and the project Voice tab) ---- */
async function speakText(text, engine, tts, extra) {
  const body = { engine, text, tts: Object.assign({}, tts, extra || {}) };
  return await apiPost("/api/voicelab/say", body);
}

function playerHTML(item, autoplay) {
  return '<div class="play-item"><div class="play-meta"><b>' + esc(item.label) + '</b></div>' +
    (item.text ? '<div class="muted play-text">' + esc(item.text.length > 220 ? item.text.slice(0, 220) + "…" : item.text) + '</div>' : "") +
    '<audio controls ' + (autoplay ? "autoplay " : "") + 'src="' + item.url + '"></audio>' +
    '<a class="btn small ghost" href="' + item.url + '?download=1" download>⬇ mp3</a></div>';
}

/* ---- project Voice tab: hear it right here ---- */
async function hearHere() {
  const { engine, tts } = readTts("v");
  const text = document.getElementById("vHearText").value.trim();
  const st = document.getElementById("vHearStatus");
  if (!text) { toast("Type some text first"); return; }
  st.textContent = "Generating…";
  const t0 = Date.now();
  const res = await speakText(text, engine, tts);
  if (res.error) { st.textContent = ""; toast(res.error); return; }
  st.textContent = "done in " + ((Date.now() - t0) / 1000).toFixed(1) + " s";
  const list = document.getElementById("vHearList");
  list.insertAdjacentHTML("afterbegin", playerHTML({ url: res.url, label: ttsLabel(engine, tts), text }, true));
}

async function hearSegments() {
  const { engine, tts } = readTts("v");
  const segs = ((state.segments && state.segments.youtube) || []).filter(s => (s.narration || "").trim()).slice(0, 3);
  if (!segs.length) { toast("No segments with narration yet"); return; }
  const st = document.getElementById("vHearStatus");
  const list = document.getElementById("vHearList");
  list.scrollIntoView({ behavior: "smooth", block: "center" });
  for (let i = 0; i < segs.length; i++) {
    const sg = segs[i];
    st.textContent = "Voicing " + sg.id + " (" + (i + 1) + "/" + segs.length + ")…";
    const res = await speakText(sg.narration, engine, tts, { seg_speed: sg.speed || 1 });
    if (res.error) { st.textContent = ""; toast(res.error); return; }
    list.insertAdjacentHTML("beforeend", playerHTML({ url: res.url, label: sg.id + " · " + ttsLabel(engine, tts), text: sg.narration }, i === 0));
  }
  st.textContent = "";
}

/* ---- Voice Lab (no project needed) ---- */
state.lab = { engine: "kokoro", tts: {}, text: "", history: [] };
const LAB_SAMPLES = [
  ["Conversational", "Okay, so here's the thing. Nobody expected him to come back, not after what happened. But he did. And honestly? He looked better than ever."],
  ["Dramatic", "The door slammed shut. Silence. Then, from somewhere deep in the dark... a single, slow footstep."],
  ["Chatterbox tags", "Okay, I am not going to lie, [chuckle] that was not the plan. [sigh] But somehow it worked. [laugh] Honestly, I still cannot believe it."],
  ["Hype", "Three seconds left, down by one, and he pulls up from way downtown. Are you kidding me? It's good!"],
];

function openLab() {
  state.current = null;
  renderProjectList();
  $("emptyState").classList.add("hidden");
  $("projectView").classList.add("hidden");
  $("labView").classList.remove("hidden");
  renderLab();
}

function renderLab() {
  const L = state.lab;
  const engOpts = state.bootstrap.engines.map(e => '<option value="' + e[0] + '"' + (e[0] === L.engine ? " selected" : "") + '>' + esc(e[1]) + '</option>').join("");
  const defs = (state.bootstrap.default_config && state.bootstrap.default_config.tts) || {};
  $("labView").innerHTML =
    '<h1 style="margin-top:0">🎙 Voice Lab</h1>' +
    '<p class="muted">Type anything, pick an engine and a voice, and listen right here in the browser. Nothing is saved to a project. ' +
      'ElevenLabs and MiniMax use your credits (keys in 🔑 API keys); Edge needs internet; Kokoro runs on your PC.</p>' +
    '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">' +
      '<div class="card"><h3 style="margin-top:0">Voice</h3>' +
        '<label>Engine</label><select id="labEngine" onchange="ttsEngineChange(\'lab\');state.lab.engine=this.value">' + engOpts + '</select>' +
        ttsControlsHTML("lab", Object.assign({}, defs, L.tts), L.engine) +
      '</div>' +
      '<div class="card"><h3 style="margin-top:0">Text</h3>' +
        '<textarea id="labText" rows="9" placeholder="Type or paste what the voice should say…" oninput="state.lab.text=this.value;labCount()">' + esc(L.text) + '</textarea>' +
        '<div class="muted" id="labCount" style="margin:4px 0 8px"></div>' +
        '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">' +
          LAB_SAMPLES.map((x, i) => '<button class="btn small ghost" onclick="labSample(' + i + ')">' + esc(x[0]) + '</button>').join("") +
        '</div>' +
        '<button id="labGo" class="btn primary" onclick="labGenerate()">▶ Generate &amp; play</button> ' +
        '<span id="labStatus" class="muted"></span>' +
      '</div>' +
    '</div>' +
    '<div id="labHistory">' + L.history.map((h, i) => playerHTML(h, false)).join("") + '</div>';
  labCount();
}

function labCount() {
  const el = document.getElementById("labCount");
  if (!el) return;
  const n = (state.lab.text || "").length;
  el.textContent = n + " characters" + (n > 5000 ? " (max 5000)" : "") + " · tags like [excited] work on ElevenLabs v3; [laugh] [sigh] [chuckle]... work on Chatterbox Turbo; other engines drop them";
}

function labSample(i) {
  state.lab.text = LAB_SAMPLES[i][1];
  document.getElementById("labText").value = state.lab.text;
  labCount();
}

async function labGenerate() {
  const { engine, tts } = readTts("lab");
  state.lab.engine = engine;
  state.lab.tts = tts;
  const text = document.getElementById("labText").value.trim();
  const st = document.getElementById("labStatus");
  const btn = document.getElementById("labGo");
  if (!text) { toast("Type some text first"); return; }
  btn.disabled = true;
  const t0 = Date.now();
  const tick = setInterval(() => {
    st.textContent = "Generating… " + ((Date.now() - t0) / 1000).toFixed(0) + " s" +
      (engine === "kokoro" && Date.now() - t0 > 15000 ? " (first Kokoro run downloads the ~350 MB model)" : "");
  }, 500);
  st.textContent = "Generating…";
  let res;
  try { res = await speakText(text, engine, tts); } finally { clearInterval(tick); btn.disabled = false; }
  if (res.error) { st.textContent = ""; toast(res.error); document.getElementById("labHistory").insertAdjacentHTML("afterbegin", '<div class="play-item bad">⚠ ' + esc(res.error) + '</div>'); return; }
  st.textContent = "done in " + ((Date.now() - t0) / 1000).toFixed(1) + " s";
  const item = { url: res.url, label: ttsLabel(engine, tts), text };
  state.lab.history.unshift(item);
  document.getElementById("labHistory").innerHTML = state.lab.history.map((h, i) => playerHTML(h, i === 0)).join("");
}

function runVoice(preview, force) {
  const engine = (state.detail.config.tts && state.detail.config.tts.engine) || "edge";
  const flags = { engine };
  if (preview) flags.preview = true;
  if (force) { flags.force = true; flags.yes = true; }
  startJob("tts", flags, force ? "Regenerate all audio" : (preview ? "Preview voice" : "Generate voice-over"));
}

/* ------------------------------------------------------------------ */
/* outputs                                                             */
/* ------------------------------------------------------------------ */
function audioList(folder, title) {
  const files = (state.detail.files[folder] || []).filter(f => f.kind === "audio");
  if (!files.length) return "";
  return '<div class="section"><h3>' + title + '</h3><div class="card">' +
    files.map((f) =>
      '<div style="margin-bottom:10px"><div class="muted" style="font-size:11px">' + esc(f.name) + '</div>' +
      '<audio controls style="width:100%" src="' + fileUrl(folder + "/" + f.name) + '"></audio></div>').join("") +
    '</div></div>';
}

function renderOutputs(c) {
  const d = state.detail, out = d.outputs;
  const sheets = (d.files.sheets || []).filter(f => f.kind === "image");
  const clips = (d.files.clips || []).filter(f => f.kind === "video");
  const downloads = [
    ["Premiere XML", "premiere_sequence.xml", out.premiere],
    ["VideoPad project", "videopad_project.vpj", out.videopad],
    ["Subtitles (.srt)", "recap_subtitles.srt", out.srt],
    ["On-screen text (.srt)", "recap_onscreen.srt", out.onscreen_srt],
    ["Chapters", "chapters.txt", out.chapters],
    ["Shot manifest", "shot_manifest.csv", out.shot_manifest],
    ["Credits / source log", "credits.txt", out.credits],
    ["Review sheet (Excel)", "review_sheet.csv", out.review_csv],
  ].filter(([, , ok]) => ok);

  c.innerHTML =
    (out.video
      ? '<div class="section"><h3>Finished video</h3><div class="card">' +
        '<video controls style="width:100%;max-height:420px;border-radius:8px" src="' + fileUrl("recap_final.mp4") + '"></video>' +
        '<div style="margin-top:8px"><a class="btn small" href="' + fileUrl("recap_final.mp4") + '" download>Download</a></div></div></div>'
      : "") +
    (sheets.length
      ? '<div class="section"><h3>Contact sheets</h3><div class="media-grid">' +
        sheets.map((f) => mediaItem(f.name, f.kind, fileUrl("sheets/" + f.name))).join("") + '</div></div>'
      : "") +
    (clips.length
      ? '<div class="section"><h3>Cut clips</h3><div class="media-grid">' +
        clips.map((f) => mediaItem(f.name, f.kind, fileUrl("clips/" + f.name))).join("") + '</div></div>'
      : "") +
    audioList("audio", "Voice-over (audio/)") +
    audioList("audio_preview", "Preview audio (audio_preview/)") +
    (downloads.length
      ? '<div class="section"><h3>Files</h3><div class="card"><div class="row" style="display:flex;gap:8px;flex-wrap:wrap">' +
        downloads.map(([label, file]) =>
          '<a class="btn small" href="' + fileUrl(file) + '" download>' + esc(label) + '</a>').join("") +
        '</div></div></div>'
      : "") +
    (!out.video && !sheets.length && !clips.length && !downloads.length
      ? '<div class="card muted">No outputs yet — run a build step.</div>' : "");
}

/* ------------------------------------------------------------------ */
/* settings                                                            */
/* ------------------------------------------------------------------ */
function moduleOpts(selected) {
  return state.bootstrap.modules.map(m =>
    '<option value="' + m[0] + '"' + (m[0] === selected ? " selected" : "") + '>' + esc(m[1]) + '</option>').join("");
}

function renderSettings(c) {
  const p = state.detail.project, cfg = state.detail.config || {};
  const tk = cfg.tiktok || {}, sub = cfg.subtitles || {};
  const recap = isRecap();
  c.innerHTML =
    '<div class="grid cols2">' +
      '<div class="card">' +
        '<h3 style="margin-top:0">Project</h3>' +
        '<label>Module</label><select id="sModule">' + moduleOpts(p.module) + '</select>' +
        '<label>Topic / title</label><input id="sTopic" value="' + esc(p.topic || "") + '">' +
        (isComic() ? '<label>Reading direction</label><select id="sReading">' +
          [['ltr', 'Left to right (western, manhwa)'], ['rtl', 'Right to left (manga)']].map(r => '<option value="' + r[0] + '"' + ((p.reading || 'ltr') === r[0] ? " selected" : "") + '>' + r[1] + '</option>').join("") + '</select>' : "") +
        (recap ? '<label>Style</label><select id="sStyle">' +
          ['retell', 'commentary', 'mixed'].map(s => '<option value="' + s + '"' + (p.style === s ? " selected" : "") + '>' + s + '</option>').join("") +
          '</select>' : "") +
        '<div class="form-row">' +
          '<div><label>Target length</label><input id="sTarget" value="' + esc(p.target_length || "") + '" placeholder="8:00"></div>' +
          '<div><label>Platform</label><select id="sPlatform">' +
            ['youtube', 'tiktok', 'both'].map(s => '<option value="' + s + '"' + (p.platform === s ? " selected" : "") + '>' + s + '</option>').join("") +
          '</select></div>' +
        '</div>' +
        '<label>Voice text style (tags)</label><select id="sTtsMode">' +
          ['plain', 'light', 'heavy'].map(s => '<option value="' + s + '"' + (p.tts_mode === s ? " selected" : "") + '>' + s + '</option>').join("") +
        '</select>' +
        '<label>Voice card</label><input id="sVoiceCard" value="' + esc(p.voice_card || "") + '">' +
        '<label class="check"><input type="checkbox" id="sMusic"' + (p.music ? " checked" : "") + '> background music bed</label>' +
        '<label class="check"><input type="checkbox" id="sCaptions"' + (p.captions ? " checked" : "") + '> captions</label>' +
        '<button class="btn primary" style="margin-top:14px" onclick="saveProjectSettings()">Save project</button>' +
      '</div>' +
      '<div class="card">' +
        '<h3 style="margin-top:0">Render config</h3>' +
        '<div class="form-row3">' +
          '<div><label>fps</label><input id="cFps" value="' + esc(cfg.fps != null ? cfg.fps : 24) + '"></div>' +
          '<div><label>width</label><input id="cWidth" value="' + esc(cfg.width != null ? cfg.width : 1920) + '"></div>' +
          '<div><label>height</label><input id="cHeight" value="' + esc(cfg.height != null ? cfg.height : 1080) + '"></div>' +
        '</div>' +
        '<div class="form-row">' +
          '<div><label>Fill (different aspect)</label><select id="cFill">' +
            ['pad', 'blur'].map(s => '<option value="' + s + '"' + (cfg.fill === s ? " selected" : "") + '>' + s + '</option>').join("") + '</select></div>' +
          '<div><label>Music volume</label><input id="cMusicVol" value="' + esc(cfg.music_volume != null ? cfg.music_volume : 0.12) + '"></div>' +
        '</div>' +
        '<label>TikTok (w × h × fps)</label>' +
        '<div class="form-row3">' +
          '<div><input id="cTkW" value="' + esc(tk.width != null ? tk.width : 1080) + '" placeholder="width"></div>' +
          '<div><input id="cTkH" value="' + esc(tk.height != null ? tk.height : 1920) + '" placeholder="height"></div>' +
          '<div><input id="cTkFps" value="' + esc(tk.fps != null ? tk.fps : 30) + '" placeholder="fps"></div>' +
        '</div>' +
        '<label>Subtitles (chars/line × lines)</label>' +
        '<div class="form-row">' +
          '<div><input id="cSubChars" value="' + esc(sub.max_chars_per_line != null ? sub.max_chars_per_line : 42) + '" placeholder="chars/line"></div>' +
          '<div><input id="cSubLines" value="' + esc(sub.max_lines != null ? sub.max_lines : 2) + '" placeholder="lines"></div>' +
        '</div>' +
        (isComic() ? comicConfigCard(cfg.comic || {}) : "") +
        '<button class="btn primary" style="margin-top:14px" onclick="saveConfigSettings()">Save config</button>' +
      '</div>' +
    '</div>' +
    '<div class="section" style="margin-top:20px">' +
      '<h3>Maintenance</h3>' +
      '<div class="card">' +
        '<span class="badge ' + (state.detail.engine_current ? "good" : "amber") + '">engine ' + (state.detail.engine_current ? "up to date" : "outdated") + '</span>' +
        '<div style="margin-top:10px">' +
          '<button class="btn" onclick="syncEngine()">Update engine (recap.py)</button> ' +
          '<button class="btn ghost" onclick="apiPost(\'/api/projects/' + enc(state.current) + '/open\')">📂 Open folder</button>' +
        '</div>' +
        '<p class="muted" style="margin-top:8px">' + esc(state.detail.folder) + '</p>' +
      '</div>' +
    '</div>';
}

async function saveProjectSettings() {
  const recap = isRecap();
  const project = {
    module: document.getElementById("sModule").value,
    topic: document.getElementById("sTopic").value,
    target_length: document.getElementById("sTarget").value,
    platform: document.getElementById("sPlatform").value,
    tts_mode: document.getElementById("sTtsMode").value,
    voice_card: document.getElementById("sVoiceCard").value,
    music: document.getElementById("sMusic").checked,
    captions: document.getElementById("sCaptions").checked,
  };
  if (recap) project.style = document.getElementById("sStyle").value;
  if (isComic() && document.getElementById("sReading")) project.reading = document.getElementById("sReading").value;
  const res = await apiPost("/api/projects/" + enc(state.current) + "/settings", { project });
  if (res.error) { toast(res.error); return; }
  toast("Project saved ✓");
  await refreshProjects();
  await loadDetail();
  renderHeader();
  renderTab();
}

function comicConfigCard(cm) {
  const sel = (id, val, opts) => '<select id="' + id + '">' + opts.map(o => '<option value="' + o + '"' + (val === o ? " selected" : "") + '>' + o + '</option>').join("") + '</select>';
  return '<label>Comic camera (push-in zoom × swipe seconds × pages per PDF)</label>' +
    '<div class="form-row3">' +
      '<div><input id="cmZoom" value="' + esc(cm.zoom != null ? cm.zoom : 1.12) + '"></div>' +
      '<div><input id="cmEnter" value="' + esc(cm.enter_sec != null ? cm.enter_sec : 0.35) + '"></div>' +
      '<div><input id="cmPdf" value="' + esc(cm.pdf_pages != null ? cm.pdf_pages : 30) + '"></div>' +
    '</div>' +
    '<div class="form-row">' +
      '<div><label>New page entrance</label>' + sel("cmTurn", cm.page_turn || "slide", ["slide", "fade", "pop", "cut"]) + '</div>' +
      '<div><label>Next panel, same page</label>' + sel("cmSame", cm.same_panel_move || "slide", ["slide", "cut"]) + '</div>' +
    '</div>';
}

async function saveConfigSettings() {
  const config = {
    fps: parseFloat(document.getElementById("cFps").value) || 24,
    width: parseInt(document.getElementById("cWidth").value) || 1920,
    height: parseInt(document.getElementById("cHeight").value) || 1080,
    fill: document.getElementById("cFill").value,
    music_volume: parseFloat(document.getElementById("cMusicVol").value) || 0.12,
    tiktok: {
      width: parseInt(document.getElementById("cTkW").value) || 1080,
      height: parseInt(document.getElementById("cTkH").value) || 1920,
      fps: parseInt(document.getElementById("cTkFps").value) || 30,
    },
    subtitles: {
      max_chars_per_line: parseInt(document.getElementById("cSubChars").value) || 42,
      max_lines: parseInt(document.getElementById("cSubLines").value) || 2,
    },
  };
  if (isComic() && document.getElementById("cmZoom")) {
    config.comic = {
      zoom: parseFloat(document.getElementById("cmZoom").value) || 1.12,
      enter_sec: parseFloat(document.getElementById("cmEnter").value) || 0.35,
      page_turn: document.getElementById("cmTurn").value,
      same_panel_move: document.getElementById("cmSame").value,
      pdf_pages: parseInt(document.getElementById("cmPdf").value) || 30,
    };
  }
  const res = await apiPost("/api/projects/" + enc(state.current) + "/config", { config });
  if (res.error) { toast(res.error); return; }
  toast("Config saved ✓");
  await loadDetail();
}

async function syncEngine() {
  const res = await apiPost("/api/projects/" + enc(state.current) + "/sync", {});
  if (res.error) { toast(res.error); return; }
  toast("Engine updated ✓");
  await loadDetail();
  renderHeader();
}

/* ------------------------------------------------------------------ */
/* new project modal                                                   */
/* ------------------------------------------------------------------ */
function newProjectModal() {
  openModal(
    '<h2>New project</h2>' +
    '<label>Project name</label><input id="npName" placeholder="e.g. Solo Leveling S01E05">' +
    '<div class="form-row">' +
      '<div><label>Module</label><select id="npModule">' + moduleOpts("movie_recap") + '</select></div>' +
      '<div><label>Target length</label><input id="npTarget" placeholder="8:00"></div>' +
    '</div>' +
    '<label>Topic / title</label><input id="npTopic" placeholder="e.g. Kobe 81-point game">' +
    '<div class="form-row">' +
      '<div><label>Platform</label><select id="npPlatform">' +
        ['youtube', 'tiktok', 'both'].map(s => '<option value="' + s + '">' + s + '</option>').join("") + '</select></div>' +
      '<div><label>Voice style</label><select id="npTtsMode">' +
        ['plain', 'light', 'heavy'].map(s => '<option value="' + s + '">' + s + '</option>').join("") + '</select></div>' +
    '</div>' +
    '<label class="check"><input type="checkbox" id="npMusic"> background music bed</label>' +
    '<div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end">' +
      '<button class="btn ghost" onclick="closeModal()">Cancel</button>' +
      '<button class="btn primary" onclick="submitNewProject()">Create project</button>' +
    '</div>');
  document.getElementById("npName").focus();
}

async function submitNewProject() {
  const name = document.getElementById("npName").value.trim();
  if (!name) { toast("Enter a project name."); return; }
  const project = {
    module: document.getElementById("npModule").value,
    topic: document.getElementById("npTopic").value,
    target_length: document.getElementById("npTarget").value,
    platform: document.getElementById("npPlatform").value,
    tts_mode: document.getElementById("npTtsMode").value,
    style: "retell",
    music: document.getElementById("npMusic").checked,
    captions: true,
  };
  const res = await apiPost("/api/projects", { name, project });
  if (res.error) { toast(res.error); return; }
  closeModal();
  await refreshProjects();
  await selectProject(res.name);
}

init();














/* ------------------------------------------------------------------ */
/* API keys                                                            */
/* ------------------------------------------------------------------ */
const KEY_DEFS = [  // [env name, label, help, optional placeholder]
  ["ELEVENLABS_API_KEY", "ElevenLabs", "Best quality voices. Several keys allowed (comma-separated): the tool switches key when one runs out of credits."],
  ["MINIMAX_API_KEY", "MiniMax", "Alternative voice engine (speech-2.6-hd). Several keys allowed."],
  ["HF_TOKEN", "Hugging Face token (Pocket TTS voice cloning)", "Free. First accept the terms at huggingface.co/kyutai/pocket-tts, then make a Read token at huggingface.co/settings/tokens and paste it here (one token, starts with hf_). Restart Recap Studio after saving; the first cloning run downloads the weights, so it needs internet once.", "hf_..."],
];

function keyChips(list) {
  return list.length
    ? list.map((x) => '<span class="badge good">' + esc(x) + "</span>").join(" ")
    : '<span class="badge">not set</span>';
}

async function keysModal() {
  const data = await apiGet("/api/keys");
  const keys = data.keys || {};
  openModal(
    '<h2 style="margin-top:0">🔑 API keys</h2>' +
    '<p class="muted">Saved on this computer in <code>keys.env</code> and used by every project. ' +
    'Saved keys are never shown in full (only the last 4 characters). ' +
    '<b>Edge-TTS needs no key</b> - it is free.</p>' +
    KEY_DEFS.map(([name, label, help, ph]) =>
      '<div class="card" style="margin-bottom:12px">' +
        '<div style="display:flex;justify-content:space-between;align-items:center"><b>' + label + '</b>' +
        '<span>' + keyChips(keys[name] || []) + '</span></div>' +
        '<div class="muted" style="margin:6px 0">' + help + '</div>' +
        '<label>' + ((keys[name] || []).length ? "Replace with (leave blank to keep what is saved)" : "Paste key(s)") + '</label>' +
        '<div style="display:flex;gap:8px">' +
          '<input type="password" autocomplete="off" spellcheck="false" data-key-input="' + name + '" placeholder="' + (ph || "key1, key2, ...") + '" style="flex:1">' +
          '<button class="btn small" type="button" onclick="toggleKeyVisible(\'' + name + '\')">Show</button>' +
          ((keys[name] || []).length
            ? '<button class="btn danger small" type="button" onclick="removeKey(\'' + name + '\')">Remove</button>' : "") +
        '</div>' +
      '</div>').join("") +
    '<div style="display:flex;gap:8px;justify-content:flex-end">' +
      '<button class="btn ghost" onclick="closeModal()">Close</button>' +
      '<button class="btn primary" onclick="saveKeysFromModal()">Save keys</button>' +
    '</div>');
}

function toggleKeyVisible(name) {
  const el = document.querySelector('[data-key-input="' + name + '"]');
  if (el) el.type = el.type === "password" ? "text" : "password";
}

async function postKeys(payload) {
  const r = await apiPost("/api/keys", payload);
  if (r.error) { toast(r.error); return false; }
  state.bootstrap.tools = r.tools;
  renderTools();
  if (state.detail && state.tab === "voice") renderTab();
  return true;
}

async function saveKeysFromModal() {
  const payload = {};
  document.querySelectorAll("[data-key-input]").forEach((el) => {
    if (el.value.trim()) payload[el.dataset.keyInput] = el.value.trim();
  });
  if (!Object.keys(payload).length) { toast("Nothing to save - paste a key first."); return; }
  if (await postKeys(payload)) { toast("Keys saved."); keysModal(); }
}

async function removeKey(name) {
  if (!confirm("Remove the saved " + name + " key(s) from keys.env?")) return;
  if (await postKeys({ [name]: "" })) { toast("Removed."); keysModal(); }
}

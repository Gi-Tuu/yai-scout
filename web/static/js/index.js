
const $ = (id) => document.getElementById(id);
const safeUrl = (value) => {
  try {
    const parsed = new URL(String(value || ""), window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "#";
  } catch {
    return "#";
  }
};

const state = { taskId: null, es: null, sources: new Map(), domains: new Set(), credits: 0, t0: 0, timer: null };
const EXAMPLES = [
  "What is the 2026 global AI chip market size and the market share of its major vendors?",
  "How much did open-weight model inference costs fall in 2026, and which independent sources confirm it?",
  "What practical restrictions does a 2026 national AI regulation draft place on open-weight models?"
];
const TIER = {1: ["T1", "t1"], 2: ["T2", "t2"], 3: ["T3", ""], 4: ["T4", "t4"]};
const EVENT_TYPES = ["stage_started","stage_finished","plan_ready","source_found","cost_update",
  "query_failed","budget_exceeded","stage_skipped","report_ready","run_finished","run_failed",
  "run_cancelled","stream_closed"];

EXAMPLES.forEach((q) => {
  const b = document.createElement("button");
  b.className = "ghost"; b.textContent = q;
  b.onclick = () => { $("question").value = q; };
  $("examples").appendChild(b);
});

function log(kind, data) {
  const line = `[${new Date().toLocaleTimeString()}] ${kind} ${JSON.stringify(data ?? {})}`;
  $("log").textContent += line + "\n";
  $("log").scrollTop = $("log").scrollHeight;
}
function setStatus(text) { $("status").textContent = text; }
function stageEl(name) { return document.querySelector(`.stage[data-stage="${name}"]`); }
function markStage(name, cls) {
  const el = stageEl(name);
  if (!el) return;
  el.classList.remove("active", "done");
  if (cls) el.classList.add(cls);
}
function setRunning(on) {
  $("run").disabled = on; $("cancel").disabled = !on; $("question").disabled = on;
}
function reset() {
  state.sources.clear(); state.domains.clear(); state.credits = 0;
  $("sources").innerHTML = '<div class="empty">Retrieving…</div>';
  $("plan").className = "empty"; $("plan").textContent = "Planning…";
  $("report").textContent = "The report will appear here once generated.";
  $("log").textContent = "";
  ["planning","retrieving","extracting","verifying","reporting"].forEach((s) => markStage(s, ""));
  $("c-sources").textContent = "0"; $("c-domains").textContent = "0";
  $("c-credits").textContent = "0"; $("c-elapsed").textContent = "0s";
}

function connect() {
  if (state.es) state.es.close();
  const es = new EventSource(`/api/research/${state.taskId}/events`);
  state.es = es;
  EVENT_TYPES.forEach((type) => {
    es.addEventListener(type, (ev) => {
      let data = {};
      try { data = JSON.parse(ev.data); } catch (_) {}
      handle(type, data);
    });
  });
  es.onerror = () => { log("sse_error", "will retry"); };
}

function handle(type, ev) {
  log(type, ev.payload ?? ev);
  const p = ev.payload || {};
  switch (type) {
    case "stage_started":
      markStage(p.stage, "active");
      if (p.stage === "retrieving" && Array.isArray(p.queries)) {
        $("plan").className = "empty";
        $("plan").textContent = `Retrieving ${p.queries.length} queries (mode: ${p.mode || "?"}, budget ${p.max_credits} credits)`;
      }
      break;
    case "stage_finished":
      markStage(p.stage, "done");
      break;
    case "stage_skipped":
      markStage(p.stage, "done");
      break;
    case "plan_ready": {
      const subs = p.sub_questions || [];
      $("plan").className = "";
      $("plan").innerHTML = subs.map((sq, i) =>
        `<div class="source" style="margin-bottom:8px">
           <div><b>${i + 1}. ${esc(sq.question)}</b></div>
           <div class="meta">${esc((sq.queries || []).join(" · "))}</div>
         </div>`).join("");
      break;
    }
    case "source_found": {
      if (state.sources.has(p.id)) return;
      state.sources.set(p.id, p);
      if (p.domain) state.domains.add(p.domain);
      if (state.sources.size === 1) $("sources").innerHTML = "";
      const [label, cls] = TIER[p.tier] || ["T?", ""];
      const card = document.createElement("div");
      card.className = "source";
      card.innerHTML = `<a href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener noreferrer">${esc(p.title || p.url)}</a>
        <div class="meta"><span class="tier ${cls}">${label}</span><span>${esc(p.domain || "")}</span>
        <span>${p.published_at ? new Date(p.published_at).toLocaleDateString() : "date unknown"}</span></div>`;
      $("sources").appendChild(card);
      $("c-sources").textContent = state.sources.size;
      $("c-domains").textContent = state.domains.size;
      break;
    }
    case "cost_update":
      state.credits = p.spent_credits ?? state.credits;
      $("c-credits").textContent = state.credits;
      break;
    case "run_finished":
      finish();
      break;
    case "run_failed":
      setStatus("failed"); setRunning(false); finish(true);
      break;
    case "run_cancelled":
      setStatus("cancelled"); setRunning(false);
      break;
    case "stream_closed":
      if (state.timer) return;
      break;
  }
}

async function finish(failed) {
  if (state.es) { state.es.close(); state.es = null; }
  setRunning(false);
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
  if (failed) { setStatus("failed"); return; }
  try {
    const res = await fetch(`/api/research/${state.taskId}`);
    const data = await res.json();
    const task = data.task || {};
    setStatus(task.status || "delivered");
    $("c-sources").textContent = task.stats?.sources ?? state.sources.size;
    $("c-domains").textContent = task.stats?.domains ?? state.domains.size;
    $("c-credits").textContent = task.stats?.credits ?? state.credits;
    if (task.report_md) $("report").textContent = task.report_md;
    $("src-count").textContent = `${task.stats?.sources ?? 0} sources`;
    ["planning","retrieving","extracting","verifying","reporting"].forEach((s) => markStage(s, "done"));
  } catch (err) {
    log("finish_error", String(err));
  }
}

async function start() {
  const q = $("question").value.trim();
  if (q.length < 3) return;
  reset(); setRunning(true); setStatus("starting");
  const res = await fetch("/api/research", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ question: q })
  });
  if (!res.ok) { setStatus("error"); setRunning(false); return; }
  const data = await res.json();
  state.taskId = data.task.id;
  setStatus(task_status(data.task));
  state.t0 = Date.now();
  state.timer = setInterval(() => {
    $("c-elapsed").textContent = `${Math.round((Date.now() - state.t0) / 1000)}s`;
  }, 500);
  connect();
}
function task_status(t) { return (t && t.status) || "running"; }

$("run").onclick = start;
$("cancel").onclick = async () => {
  if (!state.taskId) return;
  await fetch(`/api/research/${state.taskId}/cancel`, { method: "POST" });
  setRunning(false); setStatus("cancelled");
};

fetch("/api/healthz").then((r) => r.json()).then((h) => {
  const b = $("tavily-mode");
  b.textContent = `tavily: ${h.tavily?.mode || "?"}`;
  b.classList.add(h.tavily?.mode === "key" ? "key" : "keyless");
}).catch(() => {});

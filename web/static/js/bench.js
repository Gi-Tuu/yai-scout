
const $ = (id) => document.getElementById(id);
const state = { agents: new Set(), tasks: new Set(), timer: null, sessionId: null };
const esc = (s) => (s || "").replace(/[<>&"]/g, (c) => ({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;"}[c]));

init();
async function init() {
  const [a, t] = await Promise.all([
    fetch("/api/benchmark/agents").then((r) => r.json()),
    fetch("/api/benchmark/tasks").then((r) => r.json()),
  ]);
  a.agents.forEach((ag) => {
    const el = document.createElement("span");
    const isPublic = ["mock_good", "mock_stale"].includes(ag.id);
    el.className = isPublic ? "chip on" : "chip";
    el.textContent = `${ag.id} · ${ag.name}`;
    el.onclick = () => { toggle(state.agents, ag.id, el); };
    if (isPublic) state.agents.add(ag.id);
    $("agents").appendChild(el);
  });
  t.tasks.forEach((task) => {
    const el = document.createElement("span");
    el.className = "chip on"; el.textContent = task.id;
    el.onclick = () => { toggle(state.tasks, task.id, el); };
    state.tasks.add(task.id); $("tasks").appendChild(el);
  });
}
function toggle(set, id, el) {
  if (set.has(id)) { set.delete(id); el.classList.remove("on"); }
  else { set.add(id); el.classList.add("on"); }
}
$("run").onclick = async () => {
  if (!state.agents.size || !state.tasks.size) return;
  $("run").disabled = true; $("status").textContent = "starting…";
  const res = await fetch("/api/benchmark/run", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      agent_ids: [...state.agents],
      task_ids: [...state.tasks],
      repeats: Math.max(1, Math.min(5, Number($("repeats").value) || 1)),
      failure_injection: $("inject").checked
        ? { enabled: true, rate: 0.2, modes: ["error", "empty"] }
        : null
    })
  });
  if (!res.ok) { $("status").textContent = "failed: " + res.status; $("run").disabled = false; return; }
  const data = await res.json();
  state.sessionId = data.session.id;
  $("session-id").textContent = data.session.id;
  $("board-panel").classList.remove("hidden");
  poll();
  state.timer = setInterval(poll, 1500);
};

async function poll() {
  if (!state.sessionId) return;
  const res = await fetch(`/api/benchmark/sessions/${state.sessionId}`);
  const data = await res.json();
  const session = data.session || {};
  $("status").textContent = `${session.status} · ${data.results.length}/${(session.agent_ids || []).length * (session.task_ids || []).length} results`;
  renderBoard(data.leaderboard || [], data.pareto || null);
  renderDetail(data.results || [], data.pareto || null);
  if (session.status !== "running") { clearInterval(state.timer); $("run").disabled = false; }
}

function renderBoard(rows, pareto) {
  if (!rows.length) { $("board").innerHTML = ""; return; }
  const frontier = new Set((pareto && pareto.frontier) || []);
  $("board").innerHTML =
    `<tr><th>#</th><th>Agent</th><th>Weighted view</th><th>Accuracy</th><th>Freshness</th><th>Stale rate</th><th>Evidence quality</th><th>Claim coverage</th><th>Cost</th><th>Latency</th><th>std</th><th>success</th><th>faults</th></tr>` +
    rows.map((r, i) => `<tr>
      <td class="num">${i + 1}</td>
      <td>${esc(r.agent_id)} ${frontier.has(r.agent_id) ? `<span title="Pareto frontier">★</span>` : ""}</td>
      <td><div class="row"><span class="num">${r.score}</span><span class="bar" style="width:120px"><i style="width:${Math.round(r.score * 100)}%"></i></span></div></td>
      <td class="num">${r.numeric_accuracy}</td>
      <td class="num">${r.freshness_score ?? "-"}</td>
      <td class="num" style="color:${r.stale_rate > 0.3 ? "#f87171" : "inherit"}">${r.stale_rate}</td>
      <td class="num">${r.evidence_quality ?? "-"}</td>
      <td class="num">${r.claim_coverage ?? "-"}</td><td class="num">${r.avg_cost_usd ?? "-"}</td><td class="num">${r.avg_latency_s}s</td>
      <td class="num">${r.avg_score_std ?? "-"}</td><td class="num">${r.success_rate ?? "-"}</td><td class="num">${r.fault_count ?? 0}</td>
    </tr>`).join("");
}

function renderDetail(results, pareto) {
  const frontier = new Set((pareto && pareto.frontier) || []);
  const byTask = {};
  results.forEach((r) => { (byTask[r.task_id] ||= []).push(r); });
  $("detail").innerHTML = Object.entries(byTask).map(([taskId, items]) => {
    const rows = items.map((r) => `<tr>
      <td>${esc(r.agent_id)} ${frontier.has(r.agent_id) ? `<span title="Pareto frontier">★</span>` : ""}</td>
      <td class="num">${r.numeric_accuracy}</td>
      <td class="num">${r.score}</td>
      <td class="num">${r.freshness_score ?? "-"}</td>
      <td class="num">${r.stale_claim_rate === null ? "-" : r.stale_claim_rate}</td>
      <td class="muted" style="max-width:520px">${esc((r.answer.text || "").slice(0, 160))}
        ${(r.trace || []).length ? `<details><summary>trace (${r.trace.length})</summary><pre style="white-space:pre-wrap;font-size:11px">${esc(JSON.stringify(r.trace, null, 2))}</pre></details>` : ""}
      </td>
    </tr>`).join("");
    return `<div style="margin-bottom:14px"><div class="num" style="font-size:12px">${esc(taskId)}</div>
      <table><tr><th>Agent</th><th>Numeric accuracy</th><th>Overall score</th><th>freshness</th><th>Stale rate</th><th>Answer summary</th></tr>${rows}</table></div>`;
  }).join("");
}

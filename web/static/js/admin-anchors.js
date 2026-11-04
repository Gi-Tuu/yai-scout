
const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[<>&"]/g, (c) => ({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;"}[c]));
const safeUrl = (value) => {
  try {
    const parsed = new URL(String(value || ""), window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "#";
  } catch {
    return "#";
  }
};

let token = sessionStorage.getItem("adminToken") || "";
$("token").value = token;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {...(options.headers || {}), Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function load() {
  token = $("token").value.trim();
  sessionStorage.setItem("adminToken", token);
  try {
    const [anchors, candidates, audit] = await Promise.all([
      api("/admin/anchors"),
      api("/admin/anchors/candidates"),
      api("/admin/anchors/audit"),
    ]);
    $("status").textContent = `anchors=${anchors.anchors.length} candidates=${candidates.candidates.length}`;
    renderAnchors(anchors.anchors);
    renderCandidates(candidates.candidates);
    renderAudit(audit.audit);
  } catch (error) {
    $("status").textContent = `加载失败：${error.message}`;
  }
}

function renderAnchors(items) {
  $("anchors").innerHTML = items.map((anchor) => `<tr>
    <td><span class="badge ${anchor.status === "active" ? "ok" : "muted"}">${esc(anchor.status)}</span></td>
    <td class="mono">${esc(anchor.id)}</td>
    <td class="mono">${esc(anchor.last_value)}</td>
    <td>T${anchor.source_tier}</td>
    <td><a style="color:var(--accent)" href="${esc(safeUrl(anchor.url))}" target="_blank" rel="noopener noreferrer">${esc(anchor.url)}</a></td>
    <td class="mono">${esc(anchor.supersedes || "—")}</td>
    <td>${anchor.status === "active" && anchor.supersedes ? `<button class="danger" data-rollback="${esc(anchor.id)}">Rollback</button>` : ""}</td>
  </tr>`).join("");
}

function renderCandidates(items) {
  $("candidates").innerHTML = items.map((candidate) => `<tr>
    <td><span class="badge">${esc(candidate.accuracy_status)}</span></td>
    <td><span class="badge ${candidate.gate_decision === "auto_update" ? "ok" : "warn"}">${esc(candidate.gate_decision)}</span></td>
    <td class="mono">${esc(candidate.old_value)} → ${esc(candidate.new_value)}</td>
    <td>${candidate.confidence}</td>
    <td class="muted">${esc(candidate.gate_reason)}</td>
    <td>${candidate.accuracy_status === "pending" ? `<button data-approve="${esc(candidate.id)}">Approve</button><button class="ghost" data-reject="${esc(candidate.id)}">Reject</button>` : ""}</td>
  </tr>`).join("");
}

function renderAudit(items) {
  $("audit").innerHTML = items.map((item) => `<tr>
    <td class="mono">${item.id}</td>
    <td><span class="badge">${esc(item.action)}</span></td>
    <td class="mono">${esc(item.anchor_id)}</td>
    <td class="mono">${esc(item.related_id || "—")}</td>
    <td class="muted">${esc(item.created_at)}</td>
  </tr>`).join("");
}

async function rollback(id) {
  if (!confirm(`Rollback ${id}?`)) return;
  try {
    await api(`/admin/anchors/${id}/rollback`, {method: "POST"});
    await load();
  } catch (error) { alert(error.message); }
}
async function approve(id) {
  try {
    await api(`/admin/anchors/candidates/${id}/approve`, {method: "POST"});
    await load();
  } catch (error) { alert(error.message); }
}
async function reject(id) {
  try {
    await api(`/admin/anchors/candidates/${id}/reject`, {method: "POST"});
    await load();
  } catch (error) { alert(error.message); }
}

$("load").onclick = load;
if (token) load();

$("anchors").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-rollback]");
  if (button) rollback(button.dataset.rollback);
});
$("candidates").addEventListener("click", (event) => {
  const approveButton = event.target.closest("button[data-approve]");
  if (approveButton) { approve(approveButton.dataset.approve); return; }
  const rejectButton = event.target.closest("button[data-reject]");
  if (rejectButton) reject(rejectButton.dataset.reject);
});

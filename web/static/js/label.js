
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

const DECISIONS = ["auto_update", "review", "reject", "no_change"];
let worksheet = [];
let index = 0;
const privateMode = new URLSearchParams(location.search).get("worksheet") === "private";
const storageKey = privateMode ? "accuracyLabelsPrivate" : "accuracyLabels";
let labels = JSON.parse(localStorage.getItem(storageKey) || "{}");
$("labeler").value = localStorage.getItem("accuracyLabeler") || "";

async function init() {
  const source = privateMode ? "/static/private_worksheet.json" : "/static/accuracy_worksheet.json";
  const response = await fetch(source);
  worksheet = (await response.json()).cases;
  render();
}
function current() { return worksheet[index]; }
function render() {
  $("labeler").oninput = () => localStorage.setItem("accuracyLabeler", $("labeler").value);
  const item = current();
  if (!item) { $("casePanel").innerHTML = '<div class="muted">No cases</div>'; return; }
  const anchor = item.anchor;
  const observations = item.observations || [];
  $("progress").textContent = `${index + 1}/${worksheet.length} · labeled ${Object.keys(labels).length}`;
  $("casePanel").innerHTML = `
    <div class="progress">${item.worksheet_id} · ${esc(item.temporal_sensitivity)}</div>
    <div class="case-title">${esc(item.claim_text)}</div>
    <div class="muted" style="font-size:12px">Current anchor: ${esc(anchor.value)} · T${anchor.source_tier} · ${esc(anchor.url)}</div>
    <table style="margin-top:10px"><thead><tr><th>Sources</th><th>tier</th><th>group</th><th>value</th><th>published</th><th>reachable</th></tr></thead><tbody>
      ${observations.map((o) => `<tr><td><a style="color:var(--accent)" href="${esc(safeUrl(o.url))}" target="_blank" rel="noopener noreferrer">${esc(o.url)}</a></td><td>T${o.source_tier}</td><td>${esc(o.independent_group)}</td><td class="mono">${esc(o.value)}</td><td>${esc(o.published_at || "—")}</td><td>${o.reachable === false ? "no" : "yes"}</td></tr>`).join("")}
    </tbody></table>
    <div class="choices">
      ${DECISIONS.map((d) => `<button data-decision="${d}">${d}</button>`).join("")}
    </div>
    <div class="muted" style="font-size:12px;margin-top:8px">Your choice is saved to local localStorage; export the JSON for evaluation when finished.</div>`;
  document.querySelectorAll("[data-decision]").forEach((button) => {
    button.onclick = () => {
      labels[item.worksheet_id] = button.dataset.decision;
      localStorage.setItem(storageKey, JSON.stringify(labels));
      if (index < worksheet.length - 1) index += 1;
      render();
    };
  });
}
$("prev").onclick = () => { if (index > 0) index -= 1; render(); };
$("next").onclick = () => { if (index < worksheet.length - 1) index += 1; render(); };
$("export").onclick = () => {
  const payload = {
    version: privateMode
      ? "accuracy-gate-labels-private/0.1"
      : "accuracy-gate-labels-independent/0.1",
    labeler: $("labeler").value || "anonymous",
    labels,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = privateMode
    ? `accuracy_labels_private_${payload.labeler}.json`
    : `accuracy_labels_${payload.labeler}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  $("status").textContent = `picked ${Object.keys(labels).length}/${worksheet.length}`;
};
init();


const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[<>&"]/g, (c) => ({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;"}[c]));
let reports = [];
async function init() {
  const res = await fetch("/freshness/reports");
  reports = (await res.json()).reports || [];
  ["left", "right"].forEach((id) => {
    $(id).innerHTML = reports.map((r) => `<option value="${esc(r.id)}">${esc(r.id)} · ${esc(r.as_of)} · score ${r.overall_score ?? "—"}</option>`).join("");
  });
  if (reports.length > 1) $("right").selectedIndex = 1;
}
$("run").onclick = async () => {
  const left = $("left").value, right = $("right").value;
  if (!left || !right) return;
  const res = await fetch(`/freshness/compare?left_id=${encodeURIComponent(left)}&right_id=${encodeURIComponent(right)}`);
  if (!res.ok) { $("result").innerHTML = '<div class="panel">Comparison failed</div>'; return; }
  render(await res.json());
};
function render(d) {
  $("hint").textContent = `mode=${d.mode} · ${d.left_as_of} → ${d.right_as_of} · summary ${JSON.stringify(d.summary)}`;
  const warn = d.warning ? `<div class="warnbox">${esc(d.warning)}</div>` : "";
  const rows = d.diffs.map((x) => `<tr>
    <td><span class="badge ${x.change}">${x.change}</span></td>
    <td>${esc(x.text_left || "—")}</td>
    <td>${esc(x.text_right || "—")}</td>
    <td class="mono">${(x.numbers_left || []).join(",") || "—"} → ${(x.numbers_right || []).join(",") || "—"}</td>
    <td class="mono">${x.status_left ?? "—"} → ${x.status_right ?? "—"}</td>
    <td class="mono">${x.freshness_delta ?? "—"}</td>
    <td class="muted">+${(x.evidence_added || []).length} / −${(x.evidence_removed || []).length}</td>
  </tr>`).join("");
  $("result").innerHTML = `<div class="panel">${warn}
    <h2>Claim drift</h2>
    <table><tr><th>Change</th><th>Before</th><th>After</th><th>Value</th><th>Status</th><th>Δfreshness</th><th>Evidence</th></tr>
    ${rows || '<tr><td colspan="7" class="muted">No claims to compare</td></tr>'}</table></div>`;
}
init();

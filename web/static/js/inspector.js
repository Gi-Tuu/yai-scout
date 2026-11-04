
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

const STATUS = ["fresh", "stale", "conflicted", "insufficient", "unknown"];
let current = null;
let filter = "all";

const reportId = (location.pathname.match(/\/inspector\/([^/]+)/) || [])[1] || null;

async function init() {
  const res = await fetch("/freshness/reports");
  const data = await res.json();
  const reports = data.reports || [];
  $("list").innerHTML = reports.length ? "" : '<div class="empty">还没有报告</div>';
  reports.forEach((r) => {
    const el = document.createElement("div");
    el.className = "report" + (r.id === reportId ? " on" : "");
    el.innerHTML = `<div class="id">${esc(r.id)}</div>
      <div>score ${r.overall_score ?? "—"} · ${r.claims} claims · stale ${r.stale_claims}</div>
      <div class="id">${esc(r.created_at)}</div>`;
    el.onclick = () => load(r.id);
    $("list").appendChild(el);
  });
  if (reportId) load(reportId);
  else if (reports[0]) load(reports[0].id);
}

async function load(id) {
  const res = await fetch(`/freshness/reports/${id}`);
  if (!res.ok) { $("detail").innerHTML = '<div class="empty">报告不存在</div>'; return; }
  current = await res.json();
  document.querySelectorAll(".report").forEach((el) => el.classList.remove("on"));
  render();
}

function render() {
  const r = current;
  const verdicts = Object.fromEntries((r.verdicts || []).map((v) => [v.claim_id, v]));
  const counts = STATUS.map((s) => `${s}: ${(r.verdicts || []).filter((v) => v.status === s).length}`).join(" · ");
  const head = `<div class="muted" style="font-size:12px">
    report <span class="mono">${esc(r.id)}</span> · as_of ${esc(r.as_of)} · overall <b>${r.overall_score ?? "—"}</b> · coverage ${r.coverage == null ? "—" : Math.round(r.coverage * 100) + "%"}
    · policy ${esc(r.policy_version)} / weights ${esc(r.weights_version)} · ${counts}</div>
    <div class="toolbar" style="margin-top:10px">
      ${["all", ...STATUS].map((s) => `<button class="ghost" data-filter="${s}" ${filter === s ? 'style="border-color:#7a5314;color:var(--accent)"' : ""}>${s}</button>`).join("")}
    </div>`;
  const claims = (r.claims || []).filter((c) => {
    if (filter === "all") return true;
    return (verdicts[c.id] || {}).status === filter;
  }).map((c) => {
    const v = verdicts[c.id] || {};
    const b = v.breakdown || {};
    const anchorEvidence = (v.evidence || []).filter((e) => e.anchor_id);
    const anchorBlock = anchorEvidence.length ? `<div class="anchor-box">
      <div class="k">ANCHOR EVIDENCE · 并列展示，不自动裁决</div>
      ${anchorEvidence.map((e) => `<div class="ev">
        <div><span class="rel">${esc(e.relation)}</span><a href="${esc(safeUrl(e.url))}" target="_blank" rel="noopener noreferrer">${esc(e.title || e.url)}</a>
          <span class="badge">${esc(e.anchor_id)}</span>
          ${e.content_changed ? `<span class="badge stale">content changed</span>` : ""}</div>
        <div class="muted">T${e.tier} · 发布 ${esc(e.published_at || "unknown")} · anchor hash ${e.content_changed ? "changed" : "matched"}</div>
        <div>${esc((e.snippet || "").slice(0, 180))}</div>
      </div>`).join("")}
    </div>` : "";
    const evidence = (v.evidence || []).map((e) => `<div class="ev">
      <div><span class="rel">${esc(e.relation)}</span><a href="${esc(safeUrl(e.url))}" target="_blank" rel="noopener noreferrer">${esc(e.title || e.url)}</a></div>
      <div class="muted">${esc(e.domain)} · 发布 ${esc(e.published_at || "unknown")} · ${esc(e.evidence_kind || "unknown")} · T${e.tier} · conf ${e.relation_confidence ?? "-"}</div>
      <div class="muted">${esc(e.relation_reason || "")}</div>
      <div>${esc((e.snippet || "").slice(0, 220))}</div>
    </div>`).join("");
    return `<div class="claim">
      <div><span class="badge ${esc(v.status)}">${esc(v.status)}</span>
        <span class="badge">${esc(c.temporal_sensitivity)}</span>
        <span class="badge">${esc(c.type)}</span>
        <b class="mono">${v.score === null || v.score === undefined ? "—" : v.score + "/100"}</b>
        <span class="muted">conf ${v.confidence ?? "-"}</span></div>
      <div style="margin-top:6px">${esc(c.text)}</div>
      <div class="muted" style="font-size:12px">${esc(v.rationale || "")}</div>
      ${b.relation !== undefined ? `<div class="grid4">
        <div><div class="k">relation</div><div class="mono">${b.relation}</div><div class="bar"><i style="width:${Math.round((b.relation || 0) * 100)}%"></i></div></div>
        <div><div class="k">recency</div><div class="mono">${b.recency}</div><div class="bar"><i style="width:${Math.round((b.recency || 0) * 100)}%"></i></div></div>
        <div><div class="k">authority</div><div class="mono">${b.authority}</div><div class="bar"><i style="width:${Math.round((b.authority || 0) * 100)}%"></i></div></div>
        <div><div class="k">coverage</div><div class="mono">${b.coverage}</div><div class="bar"><i style="width:${Math.round((b.coverage || 0) * 100)}%"></i></div></div>
      </div>` : ""}
      ${v.suggestion ? `<div class="sugg">建议：${esc(v.suggestion)}</div>` : ""}
      ${anchorBlock}
      ${evidence || '<div class="muted" style="margin-top:6px">无证据（INSUFFICIENT）</div>'}
    </div>`;
  }).join("");
  $("detail").innerHTML = head + (claims || '<div class="empty">没有匹配的 claim</div>');
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.onclick = () => { filter = btn.dataset.filter; render(); };
  });
}

$("export").onclick = async () => {
  if (!current) return;
  const res = await fetch(`/freshness/reports/${current.id}/export`);
  const data = await res.json();
  const blob = new Blob([data.markdown || ""], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${current.id}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
};
$("copy").onclick = async () => {
  if (!current) return;
  await navigator.clipboard.writeText(JSON.stringify(current, null, 2));
};

init();

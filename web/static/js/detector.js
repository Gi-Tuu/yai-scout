
const $ = (id) => document.getElementById(id);
const SAMPLES = [
  "Tavily 的免费计划每月提供 500 API credits，advanced search 每次消耗 1 credit。",
  "YAI Agent Core 当前版本是 0.24.0，默认使用 Python 3.10。",
  "Bifrost 使用 Apache-2.0 许可证，自托管默认端口是 8080。"
];
SAMPLES.forEach((s, i) => {
  const b = document.createElement("button");
  b.className = "ghost"; b.textContent = `示例 ${i + 1}：${s.slice(0, 46)}…`;
  b.onclick = () => { $("answer").value = s; };
  $("samples").appendChild(b);
});
$("clear").onclick = () => { $("answer").value = ""; $("result").classList.add("hidden"); };

const STATUS_LABEL = { fresh: "fresh", stale: "stale", conflicted: "conflicted", insufficient: "insufficient", unknown: "unknown" };
const STATUS_CLASS = { fresh: "fresh", stale: "stale", conflicted: "conflicted", insufficient: "insufficient", unknown: "unknown" };

function esc(s) { return (s || "").replace(/[<>&"]/g, (c) => ({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;"}[c])); }
const safeUrl = (value) => {
  try {
    const parsed = new URL(String(value || ""), window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "#";
  } catch {
    return "#";
  }
};


$("run").onclick = async () => {
  const answer = $("answer").value.trim();
  if (answer.length < 10) return;
  $("run").disabled = true; $("hint").textContent = "检测中（每条 claim 会做一次 Tavily 检索）…";
  try {
    const res = await fetch("/api/detector", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ answer })
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    render(await res.json());
  } catch (err) {
    $("hint").textContent = "失败：" + err.message;
  } finally {
    $("run").disabled = false;
  }
};

function render(report) {
  $("result").classList.remove("hidden");
  $("overall").textContent = report.overall_score;
  $("bar").style.width = report.overall_score + "%";
  $("summary").textContent =
    `${report.claims.length} 条 claim · ${report.stale_claims} 条可能过时 · ${report.credits} credits · 报告 ${report.id}`;
  $("hint").textContent = "as_of " + report.as_of + " · coverage " + (report.coverage == null ? "—" : Math.round(report.coverage * 100) + "%");
  const byId = {};
  report.verdicts.forEach((v) => { byId[v.claim_id] = v; });
  $("claims").innerHTML = report.claims.map((c) => {
    const v = byId[c.id] || { status: "unknown", score: null, rationale: "", evidence: [] };
    const ev = (v.evidence || []).map((e) =>
      `<div class="ev"><span class="rel">${e.relation}</span><a href="${esc(safeUrl(e.url))}" target="_blank" rel="noopener noreferrer">${esc(e.title || e.url)}</a>
       <span class="muted"> · ${esc(e.domain)} · ${e.published_at ? new Date(e.published_at).toLocaleDateString() : "时间未知"} · ${esc(e.evidence_kind || "unknown")} · T${e.tier} · conf ${e.relation_confidence ?? "-"}</span><div class="muted">${esc(e.relation_reason || "")}</div>
       <div class="muted">${esc((e.snippet || "").slice(0, 160))}</div></div>`).join("");
    return `<div class="claim">
      <div><span class="badge ${STATUS_CLASS[v.status]}">${STATUS_LABEL[v.status]}</span>
        <span class="badge">${c.type}</span> <b>${v.score === null ? "—" : v.score + "/100"}</b> <span class="muted">conf ${v.confidence ?? "-"}</span></div>
      <div class="text">${esc(c.text)}</div>
      <div class="meta">${(c.numbers || []).join(" · ") || "无数字"} ${c.signals.length ? "· " + c.signals.join(",") : ""}</div>
      <div class="muted" style="font-size:12px;margin-top:4px">${esc(v.rationale)}</div>
      ${v.breakdown ? `<div class="meta">relation ${v.breakdown.relation} · recency ${v.breakdown.recency} · authority ${v.breakdown.authority} · coverage ${v.breakdown.coverage}</div>` : ""}
      ${v.suggestion ? `<div class="sugg">建议：${esc(v.suggestion)}</div>` : ""}
      ${ev}
    </div>`;
  }).join("");
}

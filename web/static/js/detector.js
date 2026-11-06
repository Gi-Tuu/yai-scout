
const $ = (id) => document.getElementById(id);
const SAMPLES = [
  "Tavily's free plan provides 500 API credits per month; advanced search consumes 1 credit per call.",
  "YAI Agent Core is currently version 0.24.0 and uses Python 3.10 by default.",
  "Bifrost is licensed under Apache-2.0 and uses port 8080 by default when self-hosted."
];
SAMPLES.forEach((s, i) => {
  const b = document.createElement("button");
  b.className = "ghost"; b.textContent = `Example ${i + 1}: ${s.slice(0, 46)}…`;
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
  $("run").disabled = true; $("hint").textContent = "Checking (one Tavily search per claim)…";
  try {
    const res = await fetch("/api/detector", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ answer })
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    render(await res.json());
  } catch (err) {
    $("hint").textContent = "Failed: " + err.message;
  } finally {
    $("run").disabled = false;
  }
};

function render(report) {
  $("result").classList.remove("hidden");
  $("overall").textContent = report.overall_score;
  $("bar").style.width = report.overall_score + "%";
  $("summary").textContent =
    `${report.claims.length} claims · ${report.stale_claims} possibly stale · ${report.credits} credits · report ${report.id}`;
  $("hint").textContent = "as_of " + report.as_of + " · coverage " + (report.coverage == null ? "—" : Math.round(report.coverage * 100) + "%");
  const byId = {};
  report.verdicts.forEach((v) => { byId[v.claim_id] = v; });
  $("claims").innerHTML = report.claims.map((c) => {
    const v = byId[c.id] || { status: "unknown", score: null, rationale: "", evidence: [] };
    const ev = (v.evidence || []).map((e) =>
      `<div class="ev"><span class="rel">${e.relation}</span><a href="${esc(safeUrl(e.url))}" target="_blank" rel="noopener noreferrer">${esc(e.title || e.url)}</a>
       <span class="muted"> · ${esc(e.domain)} · ${e.published_at ? new Date(e.published_at).toLocaleDateString() : "date unknown"} · ${esc(e.evidence_kind || "unknown")} · T${e.tier} · conf ${e.relation_confidence ?? "-"}</span><div class="muted">${esc(e.relation_reason || "")}</div>
       <div class="muted">${esc((e.snippet || "").slice(0, 160))}</div></div>`).join("");
    return `<div class="claim">
      <div><span class="badge ${STATUS_CLASS[v.status]}">${STATUS_LABEL[v.status]}</span>
        <span class="badge">${c.type}</span> <b>${v.score === null ? "—" : v.score + "/100"}</b> <span class="muted">conf ${v.confidence ?? "-"}</span></div>
      <div class="text">${esc(c.text)}</div>
      <div class="meta">${(c.numbers || []).join(" · ") || "no numbers"} ${c.signals.length ? "· " + c.signals.join(",") : ""}</div>
      <div class="muted" style="font-size:12px;margin-top:4px">${esc(v.rationale)}</div>
      ${v.breakdown ? `<div class="meta">relation ${v.breakdown.relation} · recency ${v.breakdown.recency} · authority ${v.breakdown.authority} · coverage ${v.breakdown.coverage}</div>` : ""}
      ${v.suggestion ? `<div class="sugg">Suggestion: ${esc(v.suggestion)}</div>` : ""}
      ${ev}
    </div>`;
  }).join("");
}

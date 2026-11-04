(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const STATUSES = ["fresh", "stale", "conflicted", "insufficient"];
  const requested = new URLSearchParams(location.search).get("worksheet");
  const worksheet = ["holdout", "holdout-v3", "v3"].includes(requested || "")
    ? (requested === "holdout" ? "holdout" : "holdout-v3") : "private";
  const LABELS_KEY = "freshnessVerdictLabelsV1:" + worksheet;
  const LABELER_KEY = "freshnessVerdictLabeler";
  let cases = [];
  let index = 0;
  let labels = JSON.parse(localStorage.getItem(LABELS_KEY) || "{}");

  $("labeler").value = localStorage.getItem(LABELER_KEY) || "";
  $("labeler").oninput = () => localStorage.setItem(LABELER_KEY, $("labeler").value.trim());

  async function init() {
    const response = await fetch("/label/verdict/worksheet?worksheet=" + worksheet);
    const payload = await response.json();
    cases = payload.cases || [];
    render();
  }

  function current() { return cases[index]; }

  function render() {
    const item = current();
    const panel = $("casePanel");
    if (!item) {
      panel.textContent = "no cases";
      return;
    }
    $("progress").textContent = `${worksheet} ${index + 1}/${cases.length} · labeled ${Object.keys(labels).length}`;
    panel.className = "";
    panel.innerHTML = "";
    const title = document.createElement("div");
    title.className = "case-title";
    title.textContent = item.claim.text;
    panel.appendChild(title);
    const meta = document.createElement("div");
    meta.className = "muted mono";
    meta.textContent = `${item.id} · ${item.claim.type} · ${item.claim.temporal_sensitivity}`;
    panel.appendChild(meta);
    const selected = labels[item.id];

    const row = document.createElement("div");
    row.style.marginTop = "12px";
    STATUSES.forEach((status) => {
      const button = document.createElement("button");
      button.textContent = status;
      button.className = status === "fresh" ? "ok" : "bad";
      button.style.opacity = selected && selected !== status ? "0.45" : "1";
      button.onclick = () => {
        labels[item.id] = status;
        localStorage.setItem(LABELS_KEY, JSON.stringify(labels));
        render();
      };
      row.appendChild(button);
    });
    panel.appendChild(row);

    const table = document.createElement("table");
    table.style.marginTop = "14px";
    table.innerHTML = "<thead><tr><th>source</th><th>tier</th><th>relation</th><th>published</th><th>value</th></tr></thead>";
    const tbody = document.createElement("tbody");
    (item.evidence || []).forEach((ev) => {
      const tr = document.createElement("tr");
      [ev.url || "", `T${ev.tier || "?"}`, ev.relation || "", ev.published_at || "unknown", ev.snippet || ""].forEach((value) => {
        const td = document.createElement("td");
        td.textContent = String(value);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    panel.appendChild(table);
    $("hint").textContent = selected ? `selected: ${selected}` : "not labeled";
  }

  $("prev").onclick = () => { if (index > 0) { index -= 1; render(); } };
  $("next").onclick = () => { if (index + 1 < cases.length) { index += 1; render(); } };
  $("export").onclick = () => {
    const payload = {
      version: "freshness-verdict-labels/1.0",
      labeler: $("labeler").value.trim() || "unknown",
      labels,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "freshness-verdict-labels.json";
    link.click();
    URL.revokeObjectURL(link.href);
  };

  init().catch((error) => {
    $("casePanel").textContent = "failed to load worksheet: " + error.message;
  });
})();

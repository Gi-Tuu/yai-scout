
const labels = JSON.parse(localStorage.getItem("accuracyLabels") || "{}");
const labeler = localStorage.getItem("accuracyLabeler") || "unknown";
const payload = {
  version: "accuracy-gate-labels-independent/0.1",
  labeler,
  labels,
};
document.getElementById("json").value = JSON.stringify(payload, null, 2);
document.getElementById("meta").textContent =
  `labeler=${labeler} · labeled ${Object.keys(labels).length}`;
document.getElementById("download").onclick = () => {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `accuracy_labels_${labeler}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
};
document.getElementById("copy").onclick = async () => {
  await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
  document.getElementById("status").textContent = "Copied to clipboard";
};

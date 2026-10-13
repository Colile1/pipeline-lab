// datasets.js - list an engine's registered datasets and upload a new one.
// Every value rendered comes straight from GET/POST /api/datasets; column
// names are read from whatever the engine's own rows contain (see
// buildTable in common.js) rather than hardcoded, since prepfx and b2
// catalogue completely different fields.

async function loadDatasets() {
  const engine = document.getElementById("ds-engine").value;
  const banner = document.getElementById("ds-banner");
  const wrap = document.getElementById("ds-table-wrap");
  clearChildren(banner);
  clearChildren(wrap);
  try {
    const rows = await apiCall(`/api/datasets?engine=${encodeURIComponent(engine)}`);
    const table = buildTable(rows);
    if (table) {
      wrap.appendChild(table);
    } else {
      showBanner(wrap, "No datasets registered for this engine yet.", "info");
    }
  } catch (err) {
    showBanner(banner, err.message);
  }
}

async function submitUpload(event) {
  event.preventDefault();
  const banner = document.getElementById("upload-banner");
  clearChildren(banner);
  const form = document.getElementById("upload-form");
  const data = new FormData();
  data.append("engine", document.getElementById("up-engine").value);
  data.append("file", document.getElementById("up-file").files[0]);
  data.append("dataset_id", document.getElementById("up-id").value.trim());
  data.append("target", document.getElementById("up-target").value.trim());
  const task = document.getElementById("up-task").value;
  if (task) data.append("task", task);
  data.append("domain", document.getElementById("up-domain").value.trim() || "unspecified");

  try {
    const result = await apiCall("/api/datasets/upload", { method: "POST", body: data });
    showBanner(banner, `Registered '${result.dataset_id}' with ${result.engine}.`, "info");
    form.reset();
    document.getElementById("ds-engine").value = document.getElementById("up-engine").value;
    await loadDatasets();
  } catch (err) {
    showBanner(banner, err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("ds-engine").addEventListener("change", loadDatasets);
  document.getElementById("upload-form").addEventListener("submit", submitUpload);
  loadDatasets();
});

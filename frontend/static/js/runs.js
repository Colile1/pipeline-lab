// runs.js - list launched runs, show one run's validation summary + log,
// polling while it is still running. Every field shown comes straight
// from GET /api/runs or GET /api/runs/{id} / /log - never computed here.

let pollTimer = null;
let logOffset = 0;
let selectedRunId = null;

async function loadRunsList() {
  const banner = document.getElementById("runs-banner");
  const body = document.getElementById("runs-list-body");
  clearChildren(banner);
  clearChildren(body);
  try {
    const rows = await apiCall("/api/runs");
    if (rows.length === 0) {
      showBanner(banner, "No runs launched yet. Start one from New Experiment.", "info");
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const idCell = document.createElement("td");
      idCell.textContent = row.run_id;
      const engineCell = document.createElement("td");
      engineCell.textContent = row.engine;
      const stateCell = document.createElement("td");
      stateCell.innerHTML = `<span class="status-${stateClass(row.state)}">${row.state}</span>`;
      const actionCell = document.createElement("td");
      const btn = document.createElement("button");
      btn.className = "btn-secondary";
      btn.textContent = "View";
      btn.addEventListener("click", () => selectRun(row.run_id));
      actionCell.appendChild(btn);
      tr.append(idCell, engineCell, stateCell, actionCell);
      body.appendChild(tr);
    });
  } catch (err) {
    showBanner(banner, err.message);
  }
}

function stateClass(state) {
  if (state === "succeeded") return "success";
  if (state === "running") return "running";
  if (state === "failed") return "failed";
  return "unknown";
}

function selectRun(runId) {
  selectedRunId = runId;
  logOffset = 0;
  document.getElementById("run-detail-card").hidden = false;
  document.getElementById("run-log").textContent = "";
  if (pollTimer) clearInterval(pollTimer);
  refreshRunDetail();
  pollTimer = setInterval(refreshRunDetail, 2000);
}

function renderSummary(summary) {
  const dl = document.getElementById("run-detail-summary");
  clearChildren(dl);
  const fields = [
    ["Run ID", summary.run_id],
    ["Engine", summary.engine],
    ["State", summary.state],
    ["Exit code", summary.exit_code === null ? "still running" : summary.exit_code],
    ["Progress", `${summary.completed} ${summary.progress_label} of ${summary.expected ?? "?"} ${summary.expected_label}`],
  ];
  if (summary.errors && summary.errors.length) {
    fields.push(["Errors", summary.errors.join(" | ")]);
  }
  if (summary.notes && summary.notes.length) {
    fields.push(["Notes", summary.notes.join(" | ")]);
  }
  if (summary.missingness) {
    const m = summary.missingness;
    fields.push(["Missingness requested", m.requested]);
  }
  fields.forEach(([term, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    dl.append(dt, dd);
  });
}

async function refreshRunDetail() {
  const banner = document.getElementById("run-detail-banner");
  try {
    const summary = await apiCall(`/api/runs/${encodeURIComponent(selectedRunId)}`);
    clearChildren(banner);
    renderSummary(summary);

    const logChunk = await apiCall(`/api/runs/${encodeURIComponent(selectedRunId)}/log?offset=${logOffset}`);
    if (logChunk.text) {
      document.getElementById("run-log").textContent += logChunk.text;
      document.getElementById("run-log").scrollTop = document.getElementById("run-log").scrollHeight;
    }
    logOffset = logChunk.offset;

    const resultsLink = document.getElementById("run-results-link");
    if (summary.state === "succeeded") {
      resultsLink.hidden = false;
      resultsLink.href = `/results?run_id=${encodeURIComponent(selectedRunId)}`;
    } else {
      resultsLink.hidden = true;
    }

    if (summary.state !== "running" && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
      loadRunsList();
    }
  } catch (err) {
    showBanner(banner, err.message);
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadRunsList();
  const params = new URLSearchParams(window.location.search);
  const runId = params.get("run_id");
  if (runId) selectRun(runId);
});

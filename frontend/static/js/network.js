// network.js - the layered pipeline graph, taking its shape from the
// pipeline itself: one column per stage, one node per technique, edges
// along the paths runs actually took.
//
// Drawn as positioned divs plus inline SVG for the edges, so it needs
// no charting library (frontend/README.md: no build step, no Node).

const NODE_W = 120;
const NODE_H = 34;
const LAYER_GAP = 170;
const ROW_GAP = 46;

/** Return a 0..1 shade for a value within its metric's observed range. */
function shade(value, min, max, higherIsBetter) {
  if (value === null || max === min) return 0.35;
  const scaled = (value - min) / (max - min);
  return higherIsBetter ? scaled : 1 - scaled;
}

function render(data) {
  const host = document.getElementById("network");
  clearChildren(host);

  const byLayer = {};
  data.nodes.forEach((node) => {
    byLayer[node.layer] = byLayer[node.layer] || [];
    byLayer[node.layer].push(node);
  });

  const means = data.nodes.map((n) => n.mean).filter((v) => v !== null);
  const min = Math.min(...means);
  const max = Math.max(...means);
  // For wall_seconds and rmse, lower is better.
  const higherIsBetter = !/rmse|wall|seconds|rss/.test(data.metric);

  const rows = Math.max(...data.layers.map((l) => (byLayer[l] || []).length), 1);
  const width = data.layers.length * LAYER_GAP;
  const height = rows * ROW_GAP + 70;

  const canvas = document.createElement("div");
  canvas.className = "network-canvas";
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.classList.add("network-edges");

  const position = {};
  data.layers.forEach((layer, layerIndex) => {
    const header = document.createElement("div");
    header.className = "layer-header";
    header.style.left = `${layerIndex * LAYER_GAP}px`;
    header.textContent = layer;
    canvas.appendChild(header);

    (byLayer[layer] || []).forEach((node, rowIndex) => {
      const x = layerIndex * LAYER_GAP;
      const y = 34 + rowIndex * ROW_GAP;
      position[`${layer}|${node.technique}`] = { x, y };

      const element = document.createElement("div");
      element.className = "net-node";
      element.style.left = `${x}px`;
      element.style.top = `${y}px`;
      element.style.width = `${NODE_W}px`;
      const intensity = shade(node.mean, min, max, higherIsBetter);
      element.style.background = `rgba(0, 120, 212, ${0.12 + intensity * 0.6})`;
      if (data.best_node
          && node.layer === data.best_node.layer
          && node.technique === data.best_node.technique) {
        element.classList.add("best");
      }
      element.innerHTML =
        `<span class="net-name">${node.technique}</span>`
        + `<span class="net-stat">${node.mean === null ? " - " : node.mean.toFixed(4)}`
        + ` | ${node.runs}n</span>`;
      element.title = `${node.layer} = ${node.technique}\n`
        + `${data.metric}: ${node.mean === null ? "not recorded" : node.mean}\n`
        + `${node.runs} run(s) through this node`;
      canvas.appendChild(element);
    });
  });

  const maxEdge = Math.max(...data.edges.map((e) => e.runs), 1);
  data.edges.forEach((edge) => {
    const from = position[`${edge.from_layer}|${edge.from}`];
    const to = position[`${edge.to_layer}|${edge.to}`];
    if (!from || !to) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", from.x + NODE_W);
    line.setAttribute("y1", from.y + NODE_H / 2);
    line.setAttribute("x2", to.x);
    line.setAttribute("y2", to.y + NODE_H / 2);
    line.setAttribute("stroke", "#8a8886");
    line.setAttribute("stroke-width", String(1 + (edge.runs / maxEdge) * 5));
    line.setAttribute("stroke-opacity", "0.55");
    svg.appendChild(line);
  });

  canvas.appendChild(svg);
  host.appendChild(canvas);

  document.getElementById("net-summary").textContent =
    `${data.n_runs} succeeded run(s) | coloured by ${data.metric}`
    + (data.best_node ? ` | best node: ${data.best_node.layer}=${data.best_node.technique}` : "");
  document.getElementById("net-card").hidden = false;
}

async function load() {
  const runId = document.getElementById("net-run-id").value.trim();
  const metric = document.getElementById("net-metric").value;
  const banner = document.getElementById("net-banner");
  clearChildren(banner);
  if (!runId) {
    showBanner(banner, "Enter a run-id first.", "info");
    return;
  }
  showBanner(banner, "Loading...", "info");
  try {
    const data = await apiCall(
      `/api/lab/network/${encodeURIComponent(runId)}?metric=${encodeURIComponent(metric)}`);
    clearChildren(banner);
    if (data.n_runs === 0) {
      showBanner(banner, "This run recorded no succeeded runs yet.", "info");
      document.getElementById("net-card").hidden = true;
      return;
    }
    render(data);
  } catch (err) {
    showBanner(banner, err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("net-load").addEventListener("click", load);
  document.getElementById("net-metric").addEventListener("change", () => {
    if (document.getElementById("net-run-id").value.trim()) load();
  });
  const params = new URLSearchParams(window.location.search);
  const runId = params.get("run_id");
  if (runId) {
    document.getElementById("net-run-id").value = runId;
    load();
  }
});

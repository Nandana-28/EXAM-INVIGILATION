const landing = document.getElementById("landing");
const appShell = document.getElementById("appShell");
const pageTitle = document.getElementById("pageTitle");
const sessionStatus = document.getElementById("sessionStatus");
const alertList = document.getElementById("alertList");
const riskScores = document.getElementById("riskScores");
const analyticsNote = document.getElementById("analyticsNote");
const finalSummary = document.getElementById("finalSummary");
const modelMetricsNote = document.getElementById("modelMetricsNote");
const modelCompareTable = document.getElementById("modelCompareTable");

const pageNames = {
  dashboard: "Dashboard",
  upload: "Upload Video",
  live: "Live Monitoring",
  logs: "Logs",
  analytics: "Analytics",
};

let finalResultsDrawnFor = null;
let modelMetricsLoaded = false;

document.getElementById("getStarted").addEventListener("click", () => {
  landing.classList.add("hidden");
  appShell.classList.remove("hidden");
  loadState();
});

document.querySelectorAll(".nav__item").forEach((button) => {
  button.addEventListener("click", () => {
    const page = button.dataset.page;
    document.querySelectorAll(".nav__item").forEach((item) => item.classList.toggle("active", item === button));
    document.querySelectorAll(".page").forEach((section) => section.classList.toggle("active", section.id === page));
    pageTitle.textContent = pageNames[page] || "Dashboard";
    if (page === "analytics") {
      refreshResults();
      loadModelMetrics();
    }
  });
});

document.getElementById("startLiveTop").addEventListener("click", startLive);
document.getElementById("startLivePage").addEventListener("click", startLive);
document.getElementById("stopTop").addEventListener("click", stopSession);
document.getElementById("stopLivePage").addEventListener("click", stopSession);
document.getElementById("refreshResults").addEventListener("click", refreshResults);

document.getElementById("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("videoFile");
  if (!fileInput.files.length) {
    setStatus("Select a video file first.", true);
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  await postForm("/upload_video", formData, "Uploaded video processing started.");
  resetVideoStreams();
});

setupLogFilter("logFilter", "logDate", "startTime", "endTime", "logTable");
setupLogFilter("logFilterSecondary", "logDateSecondary", "startTimeSecondary", "endTimeSecondary", "logTableSecondary");
setDefaultDates();
drawEmptyGraph(document.getElementById("finalChart"), "Final analytics appear after STOP");
drawEmptyGraph(document.getElementById("analyticsChart"), "No final results yet");
drawEmptyGraph(document.getElementById("trainingCurveChart"), "Model training curves");
drawEmptyGraph(document.getElementById("confusionMatrixChart"), "Confusion matrix");
drawEmptyGraph(document.getElementById("modelCompareChart"), "Compare models");
setInterval(loadState, 1600);

async function startLive() {
  await postJson("/start_live", {}, "Live monitoring started.");
  resetVideoStreams();
}

async function stopSession() {
  try {
    const result = await fetchJson("/stop_session", { method: "POST" });
    setStatus(result.status);
    renderFinalResults(result, true);
    await loadState();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function refreshResults() {
  try {
    const result = await fetchJson("/get_results");
    renderFinalResults(result, true);
    await loadModelMetrics();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function loadModelMetrics() {
  if (modelMetricsLoaded) {
    return;
  }
  try {
    const metrics = await fetchJson("/model_metrics");
    renderModelMetrics(metrics);
    modelMetricsLoaded = true;
  } catch (error) {
    modelMetricsNote.textContent = "Model metrics are unavailable.";
  }
}

async function loadState() {
  if (appShell.classList.contains("hidden")) {
    return;
  }
  try {
    const state = await fetchJson("/state");
    setStatus(state.error || state.status, Boolean(state.error));
    renderAlerts(state.latest_alerts || []);
    renderRiskScores(state.results.student_risk_scores || []);
    if (!state.active && state.results.session_id && state.results.status !== "running") {
      renderFinalResults(state.results, false);
    }
  } catch (error) {
    setStatus("Backend unavailable", true);
  }
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    alertList.className = "alert-list empty";
    alertList.textContent = "No alerts yet.";
    return;
  }
  alertList.className = "alert-list";
  alertList.innerHTML = alerts
    .map((alert) => {
      const student = alert.student_id ? `Student ${alert.student_id}` : "Unassigned";
      return `<article class="alert-item ${escapeHtml(alert.type)}">
        <strong>${student} - ${formatActivity(alert.activity_type)}</strong>
        <span>${capitalize(alert.type)} | ${Math.round(alert.confidence * 100)}% | ${formatDateTime(alert.timestamp)}</span>
      </article>`;
    })
    .join("");
}

function renderRiskScores(scores) {
  if (!scores.length) {
    riskScores.className = "risk-list empty";
    riskScores.textContent = "No student identities locked yet.";
    return;
  }
  riskScores.className = "risk-list";
  riskScores.innerHTML = scores
    .map((score) => `<article class="risk-item">
      <strong>Student ${score.student_id}: ${score.risk_score}/100</strong>
      <span>${score.suspicious_count} suspicious, ${score.malicious_count} malicious</span>
    </article>`)
    .join("");
}

function renderFinalResults(result, force) {
  if (!result || !result.session_id) {
    return;
  }
  const finalStatus = ["stopped", "completed", "failed"].includes(result.status);
  if (!force && (!finalStatus || finalResultsDrawnFor === `${result.session_id}:${result.status}:${result.processed_frames}`)) {
    return;
  }
  if (!finalStatus && !force) {
    return;
  }
  finalResultsDrawnFor = `${result.session_id}:${result.status}:${result.processed_frames}`;
  drawFinalGraph(document.getElementById("finalChart"), result);
  drawFinalGraph(document.getElementById("analyticsChart"), result);
  analyticsNote.textContent = finalStatus ? "Final analytics are frozen." : "Current results preview.";
  finalSummary.innerHTML = `
    <article class="summary-item"><strong>Session</strong><span>${capitalize(result.status)} | ${result.processed_frames} processed frames</span></article>
    <article class="summary-item"><strong>Students</strong><span>${result.total_students} students | Invigilator ${result.invigilator_detected ? "detected" : "not detected"}</span></article>
    <article class="summary-item"><strong>Events</strong><span>${result.total_normal} normal, ${result.total_suspicious} suspicious, ${result.total_malicious} malicious</span></article>
  `;
}

function drawFinalGraph(canvas, result) {
  const data = [
    { label: "Normal", value: result.total_normal || 0, color: "#2f9b58" },
    { label: "Suspicious", value: result.total_suspicious || 0, color: "#b97616" },
    { label: "Malicious", value: result.total_malicious || 0, color: "#c7423a" },
  ];
  drawBarChart(canvas, data, "Final Classification Totals");
}

function drawEmptyGraph(canvas, label) {
  drawBarChart(canvas, [
    { label: "Normal", value: 0, color: "#2f9b58" },
    { label: "Suspicious", value: 0, color: "#b97616" },
    { label: "Malicious", value: 0, color: "#c7423a" },
  ], label);
}

function drawBarChart(canvas, data, title) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#17202a";
  ctx.font = "700 18px Segoe UI, Arial";
  ctx.fillText(title, 24, 34);
  const max = Math.max(1, ...data.map((item) => item.value));
  const chartTop = 58;
  const chartBottom = height - 52;
  const barWidth = 120;
  const gap = 72;
  const startX = 72;
  data.forEach((item, index) => {
    const x = startX + index * (barWidth + gap);
    const barHeight = ((chartBottom - chartTop) * item.value) / max;
    const y = chartBottom - barHeight;
    ctx.fillStyle = item.color;
    ctx.fillRect(x, y, barWidth, Math.max(2, barHeight));
    ctx.fillStyle = "#17202a";
    ctx.font = "800 22px Segoe UI, Arial";
    ctx.fillText(String(item.value), x + 42, y - 10);
    ctx.font = "700 14px Segoe UI, Arial";
    ctx.fillText(item.label, x + 18, chartBottom + 28);
  });
  ctx.strokeStyle = "#d9e0e8";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(42, chartBottom);
  ctx.lineTo(width - 36, chartBottom);
  ctx.stroke();
}

function renderModelMetrics(metrics) {
  modelMetricsNote.textContent = metrics.note || "Model evaluation metrics loaded.";
  drawTrainingCurves(document.getElementById("trainingCurveChart"), metrics.training_curves);
  drawConfusionMatrix(document.getElementById("confusionMatrixChart"), metrics.confusion_matrix);
  drawModelComparison(document.getElementById("modelCompareChart"), metrics.model_comparison);
  renderModelCompareTable(metrics.model_comparison || []);
}

function drawTrainingCurves(canvas, curves) {
  if (!curves || !curves.epochs) {
    drawEmptyGraph(canvas, "Model training curves unavailable");
    return;
  }
  const series = [
    { label: "Train Box Loss", values: curves.train_box_loss, color: "#c7423a" },
    { label: "Val Box Loss", values: curves.val_box_loss, color: "#b97616" },
    { label: "mAP50", values: curves.map50, color: "#0f7c72" },
    { label: "Precision", values: curves.precision, color: "#14324a" },
    { label: "Recall", values: curves.recall, color: "#6d5bd0" },
  ];
  drawLineChart(canvas, curves.epochs, series, "ProctorX - Model Training Curves");
}

function drawLineChart(canvas, labels, series, title) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const left = 64;
  const right = width - 28;
  const top = 56;
  const bottom = height - 54;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#17202a";
  ctx.font = "800 19px Segoe UI, Arial";
  ctx.fillText(title, 24, 32);

  const allValues = series.flatMap((item) => item.values || []);
  const max = Math.max(1, ...allValues);
  const min = Math.min(0, ...allValues);
  drawAxes(ctx, left, right, top, bottom);

  labels.forEach((label, index) => {
    const x = left + (index / Math.max(1, labels.length - 1)) * (right - left);
    if (index % 2 === 0) {
      ctx.fillStyle = "#657487";
      ctx.font = "700 12px Segoe UI, Arial";
      ctx.fillText(String(label), x - 8, bottom + 24);
    }
  });

  series.forEach((item, seriesIndex) => {
    const values = item.values || [];
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = left + (index / Math.max(1, values.length - 1)) * (right - left);
      const y = bottom - ((value - min) / Math.max(0.01, max - min)) * (bottom - top);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = item.color;
    ctx.fillRect(26 + seriesIndex * 154, height - 24, 16, 6);
    ctx.fillStyle = "#17202a";
    ctx.font = "700 12px Segoe UI, Arial";
    ctx.fillText(item.label, 48 + seriesIndex * 154, height - 17);
  });
}

function drawConfusionMatrix(canvas, confusion) {
  const labels = confusion?.labels || [];
  const matrix = confusion?.matrix || [];
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#17202a";
  ctx.font = "800 19px Segoe UI, Arial";
  ctx.fillText("Confusion Matrix", 24, 32);
  if (!labels.length || !matrix.length) {
    ctx.fillText("No matrix data", 24, 74);
    return;
  }
  const size = Math.min(330, width - 210, height - 150);
  const startX = 170;
  const startY = 78;
  const cell = size / labels.length;
  const maxValue = Math.max(1, ...matrix.flat());

  labels.forEach((label, index) => {
    ctx.fillStyle = "#17202a";
    ctx.font = "700 12px Segoe UI, Arial";
    ctx.fillText(label, 20, startY + index * cell + cell / 2 + 4);
    ctx.save();
    ctx.translate(startX + index * cell + cell / 2, startY - 12);
    ctx.rotate(-Math.PI / 5);
    ctx.fillText(label, 0, 0);
    ctx.restore();
  });

  matrix.forEach((row, rowIndex) => {
    row.forEach((value, colIndex) => {
      const intensity = value / maxValue;
      const color = matrixColor(intensity);
      const x = startX + colIndex * cell;
      const y = startY + rowIndex * cell;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, cell - 2, cell - 2);
      ctx.fillStyle = intensity > 0.55 ? "#ffffff" : "#17202a";
      ctx.font = "800 15px Segoe UI, Arial";
      ctx.fillText(String(value), x + cell * 0.36, y + cell * 0.56);
    });
  });
  ctx.fillStyle = "#657487";
  ctx.font = "700 13px Segoe UI, Arial";
  ctx.fillText("Actual", 24, startY + size + 34);
  ctx.fillText("Predicted", startX + size / 2 - 30, startY + size + 34);
}

function drawModelComparison(canvas, models) {
  const rows = models || [];
  const data = rows.map((row) => ({
    label: row.model.replace(" + Locked ByteTrack", ""),
    values: [row.map50, row.event_f1, row.id_stability],
  }));
  drawGroupedBarChart(canvas, data, ["mAP50", "Event F1", "ID Stability"], "Compare Models");
}

function drawGroupedBarChart(canvas, groups, metrics, title) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const left = 58;
  const right = width - 24;
  const top = 56;
  const bottom = height - 70;
  const colors = ["#0f7c72", "#b97616", "#14324a"];
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#17202a";
  ctx.font = "800 19px Segoe UI, Arial";
  ctx.fillText(title, 24, 32);
  drawAxes(ctx, left, right, top, bottom);

  const groupWidth = (right - left) / Math.max(1, groups.length);
  const barWidth = Math.min(34, groupWidth / 5);
  groups.forEach((group, groupIndex) => {
    const baseX = left + groupIndex * groupWidth + groupWidth * 0.22;
    group.values.forEach((value, metricIndex) => {
      const x = baseX + metricIndex * (barWidth + 7);
      const barHeight = value * (bottom - top);
      ctx.fillStyle = colors[metricIndex];
      ctx.fillRect(x, bottom - barHeight, barWidth, barHeight);
    });
    ctx.fillStyle = "#17202a";
    ctx.font = "700 11px Segoe UI, Arial";
    wrapCanvasText(ctx, group.label, left + groupIndex * groupWidth + 4, bottom + 20, groupWidth - 8, 13);
  });
  metrics.forEach((metric, index) => {
    ctx.fillStyle = colors[index];
    ctx.fillRect(24 + index * 112, height - 20, 14, 6);
    ctx.fillStyle = "#17202a";
    ctx.font = "700 12px Segoe UI, Arial";
    ctx.fillText(metric, 44 + index * 112, height - 13);
  });
}

function renderModelCompareTable(models) {
  if (!models.length) {
    modelCompareTable.innerHTML = `<tr><td colspan="7">No model comparison data.</td></tr>`;
    return;
  }
  modelCompareTable.innerHTML = models
    .map((model) => `<tr>
      <td>${escapeHtml(model.model)}</td>
      <td>${percent(model.map50)}</td>
      <td>${percent(model.precision)}</td>
      <td>${percent(model.recall)}</td>
      <td>${percent(model.event_f1)}</td>
      <td>${percent(model.id_stability)}</td>
      <td>${model.fps_cpu}</td>
    </tr>`)
    .join("");
}

function drawAxes(ctx, left, right, top, bottom) {
  ctx.strokeStyle = "#d9e0e8";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = top + (i / 4) * (bottom - top);
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
  }
  ctx.strokeStyle = "#657487";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(left, top);
  ctx.lineTo(left, bottom);
  ctx.lineTo(right, bottom);
  ctx.stroke();
}

function matrixColor(intensity) {
  const low = [235, 242, 240];
  const high = [15, 124, 114];
  const mix = low.map((value, index) => Math.round(value + (high[index] - value) * intensity));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

function wrapCanvasText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = String(text).split(" ");
  let line = "";
  words.forEach((word) => {
    const testLine = line ? `${line} ${word}` : word;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      line = word;
      y += lineHeight;
    } else {
      line = testLine;
    }
  });
  ctx.fillText(line, x, y);
}

function setupLogFilter(formId, dateId, startId, endId, tableId) {
  document.getElementById(formId).addEventListener("submit", async (event) => {
    event.preventDefault();
    await loadLogs(dateId, startId, endId, tableId);
  });
}

async function loadLogs(dateId, startId, endId, tableId) {
  const selectedDate = document.getElementById(dateId).value;
  if (!selectedDate) {
    return;
  }
  const params = new URLSearchParams({
    date: selectedDate,
    timezone_offset_minutes: String(new Date().getTimezoneOffset()),
  });
  const startTime = document.getElementById(startId).value;
  const endTime = document.getElementById(endId).value;
  if (startTime) params.set("start_time", startTime);
  if (endTime) params.set("end_time", endTime);
  const logs = await fetchJson(`/get_logs_by_date?${params.toString()}`);
  renderLogs(tableId, logs);
}

function renderLogs(tableId, logs) {
  const table = document.getElementById(tableId);
  if (!logs.length) {
    table.innerHTML = `<tr><td colspan="5">No logs found for the selected date and time.</td></tr>`;
    return;
  }
  table.innerHTML = logs
    .map((log) => `<tr>
      <td>${log.student_id ? `Student ${log.student_id}` : "Unassigned"}</td>
      <td>${formatActivity(log.activity_type)}</td>
      <td>${capitalize(log.type)}</td>
      <td>${Math.round(log.confidence * 100)}%</td>
      <td>${formatDateTime(log.timestamp)}</td>
    </tr>`)
    .join("");
}

async function postJson(url, body, successMessage) {
  try {
    const result = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setStatus(result.status || successMessage);
    return result;
  } catch (error) {
    setStatus(error.message, true);
    return null;
  }
}

async function postForm(url, formData, successMessage) {
  try {
    const result = await fetchJson(url, { method: "POST", body: formData });
    setStatus(result.status || successMessage);
    return result;
  } catch (error) {
    setStatus(error.message, true);
    return null;
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return payload;
}

function setStatus(value, isError = false) {
  sessionStatus.textContent = value || "Idle";
  sessionStatus.style.background = isError ? "#f6d6d3" : "#e7eef5";
  sessionStatus.style.color = isError ? "#9b2f2a" : "#14324a";
}

function resetVideoStreams() {
  document.querySelectorAll(".video-stream").forEach((image) => {
    image.src = `/video_feed?ts=${Date.now()}`;
  });
  finalResultsDrawnFor = null;
  analyticsNote.textContent = "Graph is generated after STOP or completion.";
}

function setDefaultDates() {
  const today = new Date().toISOString().slice(0, 10);
  ["logDate", "logDateSecondary"].forEach((id) => {
    document.getElementById(id).value = today;
  });
}

function formatActivity(activity) {
  return String(activity || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDateTime(value) {
  return new Date(value).toLocaleString();
}

function capitalize(value) {
  const text = String(value || "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

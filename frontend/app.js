const landing = document.getElementById("landing");
const appShell = document.getElementById("appShell");
const pageTitle = document.getElementById("pageTitle");
const sessionStatus = document.getElementById("sessionStatus");
const alertList = document.getElementById("alertList");
const riskScores = document.getElementById("riskScores");
const analyticsNote = document.getElementById("analyticsNote");
const finalSummary = document.getElementById("finalSummary");

const pageNames = {
  dashboard: "Dashboard",
  upload: "Upload Video",
  live: "Live Monitoring",
  logs: "Logs",
  analytics: "Analytics",
};

let finalResultsDrawnFor = null;

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
  } catch (error) {
    setStatus(error.message, true);
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

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

const defaultProfile = { name: "依杋", birthDate: "2026-05-18" };

const typeLabels = {
  feeding: "餵食",
  sleep: "睡眠",
  diaper: "尿布",
  health: "健康",
  growth: "成長",
  note: "備註",
};

const typeIcons = {
  feeding: "bottle",
  sleep: "moon",
  diaper: "diaper",
  health: "heart",
  growth: "ruler",
  note: "note",
};

const columnIcons = {
  feeding: "bottle",
  sleep: "moon",
  pee: "droplet",
  poop: "poop",
  health: "heart",
  growth: "ruler",
  note: "note",
};

const workspaceViewLabels = {
  "quick-entry": "快速記錄",
  "daily-chart": "24 小時紀錄",
  "growth-trend": "成長曲線",
  "care-timeline": "照護時間軸",
};

const state = {
  activeType: "feeding",
  growthMetric: "weight",
  growthPeriod: "day",
  workspaceView: "quick-entry",
  records: [],
  profile: { ...defaultProfile },
  selectedDate: localDateKey(),
};

const els = {
  todayLabel: document.querySelector("#todayLabel"),
  viewDateEyebrow: document.querySelector("#viewDateEyebrow"),
  viewDateHeading: document.querySelector("#viewDateHeading"),
  selectedDate: document.querySelector("#selectedDate"),
  previousDateButton: document.querySelector("#previousDateButton"),
  nextDateButton: document.querySelector("#nextDateButton"),
  todayButton: document.querySelector("#todayButton"),
  dayTableTitle: document.querySelector("#dayTableTitle"),
  timelineTitle: document.querySelector("#timelineTitle"),
  insightsTitle: document.querySelector("#insightsTitle"),
  babyName: document.querySelector("#babyName"),
  birthDate: document.querySelector("#birthDate"),
  babyAge: document.querySelector("#babyAge"),
  feedCount: document.querySelector("#feedCount"),
  sleepTotal: document.querySelector("#sleepTotal"),
  peeCount: document.querySelector("#peeCount"),
  poopCount: document.querySelector("#poopCount"),
  lastRecord: document.querySelector("#lastRecord"),
  latestWeight: document.querySelector("#latestWeight"),
  growthChart: document.querySelector("#growthChart"),
  growthLatestValue: document.querySelector("#growthLatestValue"),
  growthChange: document.querySelector("#growthChange"),
  growthRecordCount: document.querySelector("#growthRecordCount"),
  feedGap: document.querySelector("#feedGap"),
  longestSleep: document.querySelector("#longestSleep"),
  latestTemp: document.querySelector("#latestTemp"),
  recordForm: document.querySelector("#recordForm"),
  recordTime: document.querySelector("#recordTime"),
  recordsList: document.querySelector("#recordsList"),
  dayTableBody: document.querySelector("#dayTableBody"),
  filterType: document.querySelector("#filterType"),
  exportButton: document.querySelector("#exportButton"),
  clearButton: document.querySelector("#clearButton"),
  pee: document.querySelector("#pee"),
  poop: document.querySelector("#poop"),
  poopAmount: document.querySelector("#poopAmount"),
  poopColor: document.querySelector("#poopColor"),
};

function getCsrfToken() {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="))
    ?.split("=")[1] || "";
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function toDatetimeLocal(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function localDateKey(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function dateFromKey(dateKey) {
  return new Date(`${dateKey}T12:00:00`);
}

function recordDateKey(iso) {
  const date = new Date(iso);
  return localDateKey(date);
}

function isSelectedDate(iso) {
  return recordDateKey(iso) === state.selectedDate;
}

function formatTime(iso) {
  return new Intl.DateTimeFormat("zh-Hant", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function formatDateLong(date = new Date()) {
  return new Intl.DateTimeFormat("zh-Hant", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);
}

function formatDateShort(dateKey) {
  return new Intl.DateTimeFormat("zh-Hant", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(dateFromKey(dateKey));
}

function selectedDateRecords() {
  return state.records.filter((record) => isSelectedDate(record.time));
}

function setSelectedDate(dateKey) {
  const today = localDateKey();
  state.selectedDate = dateKey > today ? today : dateKey;
  els.selectedDate.value = state.selectedDate;
  renderAll();
}

function shiftSelectedDate(days) {
  const date = dateFromKey(state.selectedDate);
  date.setDate(date.getDate() + days);
  setSelectedDate(localDateKey(date));
}

function renderDateNavigation() {
  const today = localDateKey();
  const isToday = state.selectedDate === today;
  const dateLabel = formatDateShort(state.selectedDate);

  els.selectedDate.value = state.selectedDate;
  els.selectedDate.max = today;
  els.nextDateButton.disabled = isToday;
  els.todayButton.disabled = isToday;
  els.viewDateEyebrow.textContent = isToday ? "今日照護" : "歷史紀錄";
  els.viewDateHeading.textContent = isToday
    ? workspaceViewLabels[state.workspaceView]
    : `${dateLabel} · ${workspaceViewLabels[state.workspaceView]}`;
  els.dayTableTitle.textContent = isToday ? "今日生理狀態表" : `${dateLabel}生理狀態表`;
  els.timelineTitle.textContent = isToday ? "今日照護時間軸" : `${dateLabel}照護時間軸`;
  els.insightsTitle.textContent = isToday ? "今日觀察" : `${dateLabel}觀察`;
}

function setWorkspaceView(view) {
  if (!workspaceViewLabels[view]) return;
  state.workspaceView = view;

  document.querySelectorAll("[data-workspace-view]").forEach((panel) => {
    panel.hidden = panel.dataset.workspaceView !== view;
  });

  document.querySelectorAll("[data-workspace-target]").forEach((button) => {
    const isActive = button.dataset.workspaceTarget === view;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  renderDateNavigation();
}

function calculateAge(birthDate) {
  if (!birthDate) return "尚未設定";
  const start = new Date(`${birthDate}T00:00:00`);
  const now = new Date();
  const diffDays = Math.max(0, Math.floor((now - start) / 86400000));
  const weeks = Math.floor(diffDays / 7);
  const days = diffDays % 7;
  if (diffDays < 7) return `${diffDays} 天`;
  return `${weeks} 週 ${days} 天`;
}

function setActiveType(type) {
  state.activeType = type;
  document.querySelectorAll(".type-tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.type === type);
  });
  document.querySelectorAll(".dynamic-field").forEach((field) => {
    field.classList.toggle("is-visible", field.dataset.for === type);
  });
}

function getFormValue(id) {
  return document.querySelector(`#${id}`)?.value.trim() || "";
}

function buildRecord() {
  const type = state.activeType;
  const record = {
    type,
    time: els.recordTime.value,
    note: getFormValue("note"),
  };

  if (type === "feeding") {
    record.feedKind = getFormValue("feedKind");
    record.feedAmount = getFormValue("feedAmount");
  }
  if (type === "sleep") {
    record.sleepMinutes = Number(getFormValue("sleepMinutes") || 0);
  }
  if (type === "diaper") {
    record.pee = els.pee.checked;
    record.poop = els.poop.checked;
    record.poopAmount = els.poop.checked ? getFormValue("poopAmount") : "";
    record.poopColor = els.poop.checked ? getFormValue("poopColor") : "";
  }
  if (type === "health") {
    record.temperature = getFormValue("temperature");
    record.symptom = getFormValue("symptom");
  }
  if (type === "growth") {
    record.weight = getFormValue("weight");
    record.height = getFormValue("height");
  }

  return record;
}

function describeRecord(record) {
  if (record.type === "feeding") {
    return [record.feedKind, record.feedAmount].filter(Boolean).join(" · ") || "餵食紀錄";
  }
  if (record.type === "sleep") {
    return record.sleepMinutes ? `${record.sleepMinutes} 分鐘` : "睡眠紀錄";
  }
  if (record.type === "diaper") {
    const parts = [];
    if (hasPee(record)) parts.push("小便");
    if (hasPoop(record)) parts.push(describePoop(record));
    return parts.length ? parts.join(" + ") : "尿布檢查";
  }
  if (record.type === "health") {
    return [record.temperature && `${record.temperature} °C`, record.symptom].filter(Boolean).join(" · ") || "健康紀錄";
  }
  if (record.type === "growth") {
    return [
      record.weight && formatWeight(record.weight),
      record.height && `${record.height} cm`,
    ].filter(Boolean).join(" · ") || "成長紀錄";
  }
  return "一般備註";
}

function renderRecords() {
  const filter = els.filterType.value;
  const records = selectedDateRecords()
    .filter((record) => filter === "all" || record.type === filter)
    .sort((a, b) => new Date(b.time) - new Date(a.time));

  if (!records.length) {
    els.recordsList.innerHTML = `<div class="empty-state">還沒有符合條件的紀錄</div>`;
    return;
  }

  els.recordsList.innerHTML = records
    .map(
      (record) => `
        <article class="record-item">
          <div class="record-badge">${iconSvg(typeIcons[record.type])}</div>
          <div>
            <p class="record-title">${typeLabels[record.type]} · ${escapeHtml(describeRecord(record))}</p>
            <p class="record-meta">${formatTime(record.time)}</p>
            ${record.note ? `<p class="record-note">${escapeHtml(record.note)}</p>` : ""}
          </div>
          <button class="delete-button" type="button" data-delete="${record.id}" aria-label="刪除這筆紀錄">×</button>
        </article>
      `
    )
    .join("");
}

function renderDayTable() {
  const dayRecords = selectedDateRecords()
    .sort((a, b) => new Date(a.time) - new Date(b.time));

  const columns = ["feeding", "sleep", "pee", "poop", "health", "growth", "note"];
  const rows = Array.from({ length: 24 }, (_, hour) => {
    const cells = columns
      .map((type) => {
        const records = dayRecords.filter((record) => {
          if (new Date(record.time).getHours() !== hour) return false;
          if (type === "pee") return record.type === "diaper" && hasPee(record);
          if (type === "poop") return record.type === "diaper" && hasPoop(record);
          return record.type === type;
        });
        return `<td>${renderTableCell(records, type)}</td>`;
      })
      .join("");

    return `
      <tr>
        <td>${pad(hour)}:00</td>
        ${cells}
      </tr>
    `;
  });

  els.dayTableBody.innerHTML = rows.join("");
}

function renderTableCell(records, columnType) {
  if (!records.length) return "";
  return `
    <div class="table-cell-list">
      ${records
        .map(
          (record) => `
            <span class="table-chip ${record.type}">
              <strong>${formatTime(record.time).slice(-5)}</strong>
              <span class="chip-line">${iconSvg(columnIcons[columnType] || typeIcons[record.type])}
              ${escapeHtml(columnType === "pee" ? "小便" : columnType === "poop" ? describePoop(record) : describeRecord(record))}
              </span>
            </span>
          `
        )
        .join("")}
    </div>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[char];
  });
}

function iconSvg(name) {
  return `<svg class="mini-icon" aria-hidden="true"><use href="#icon-${name}"></use></svg>`;
}

function renderSummary() {
  const dayRecords = selectedDateRecords();
  const feedings = dayRecords.filter((record) => record.type === "feeding");
  const sleeps = dayRecords.filter((record) => record.type === "sleep");
  const diapers = dayRecords.filter((record) => record.type === "diaper");
  const health = dayRecords.filter((record) => record.type === "health" && record.temperature);
  const latestWeightRecord = state.records
    .filter((record) => record.type === "growth" && record.weight)
    .sort((a, b) => new Date(b.time) - new Date(a.time))[0];

  const sleepMinutes = sleeps.reduce((sum, record) => sum + Number(record.sleepMinutes || 0), 0);
  const longestSleep = sleeps.reduce((max, record) => Math.max(max, Number(record.sleepMinutes || 0)), 0);
  const lastRecord = [...dayRecords].sort((a, b) => new Date(b.time) - new Date(a.time))[0];

  els.feedCount.textContent = `${feedings.length} 次`;
  els.sleepTotal.textContent = `${(sleepMinutes / 60).toFixed(1)} 小時`;
  els.peeCount.textContent = `${diapers.filter(hasPee).length} 次`;
  els.poopCount.textContent = `${diapers.filter(hasPoop).length} 次`;
  els.lastRecord.textContent = lastRecord ? `${typeLabels[lastRecord.type]} ${formatTime(lastRecord.time)}` : "無";
  els.latestWeight.textContent = latestWeightRecord
    ? `${formatWeight(latestWeightRecord.weight)} · ${formatDateCompact(latestWeightRecord.time)}`
    : "尚無資料";
  els.longestSleep.textContent = longestSleep ? formatMinutes(longestSleep) : "尚無資料";
  els.latestTemp.textContent = health.length ? `${health.sort((a, b) => new Date(b.time) - new Date(a.time))[0].temperature} °C` : "尚無資料";
  els.feedGap.textContent = calculateFeedGap(feedings);
}

function renderGrowthChart() {
  const metric = state.growthMetric;
  const period = state.growthPeriod;
  const unit = metric === "weight" ? "kg" : "cm";
  const sourceRecords = state.records
    .filter((record) => record.type === "growth" && record[metric])
    .map((record) => ({
      time: record.time,
      value: Number(record[metric]),
    }))
    .filter((record) => Number.isFinite(record.value))
    .sort((a, b) => new Date(a.time) - new Date(b.time));
  const records = aggregateGrowthRecords(sourceRecords, period);

  document.querySelectorAll(".growth-metric-button").forEach((button) => {
    const isActive = button.dataset.growthMetric === metric;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  document.querySelectorAll(".growth-period-button").forEach((button) => {
    const isActive = button.dataset.growthPeriod === period;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  els.growthRecordCount.textContent = `${records.length} 點`;

  if (!records.length) {
    els.growthLatestValue.textContent = "尚無資料";
    els.growthChange.textContent = "尚無資料";
    els.growthChart.innerHTML = `
      <div class="growth-chart-empty">
        尚未有${metric === "weight" ? "體重" : "身高"}紀錄
      </div>
    `;
    return;
  }

  const latest = records.at(-1);
  els.growthLatestValue.textContent = formatGrowthValue(latest.value, metric);

  if (records.length > 1) {
    const previous = records.at(-2);
    const change = latest.value - previous.value;
    const sign = change > 0 ? "+" : "";
    const decimals = metric === "weight" ? 3 : 1;
    els.growthChange.textContent = `${sign}${change.toFixed(decimals)} ${unit}`;
    els.growthChange.classList.toggle("is-positive", change > 0);
    els.growthChange.classList.toggle("is-negative", change < 0);
  } else {
    els.growthChange.textContent = "需要至少 2 筆";
    els.growthChange.classList.remove("is-positive", "is-negative");
  }

  els.growthChart.innerHTML = buildGrowthChartSvg(records, metric, period);
}

function aggregateGrowthRecords(records, period) {
  const grouped = new Map();
  records.forEach((record) => {
    const date = new Date(record.time);
    const key = period === "week"
      ? weekKey(date)
      : period === "month"
        ? monthKey(date)
        : localDateKey(date);
    grouped.set(key, record);
  });
  return [...grouped.values()];
}

function weekKey(date) {
  const start = new Date(date);
  const day = start.getDay();
  const distanceFromMonday = day === 0 ? 6 : day - 1;
  start.setDate(start.getDate() - distanceFromMonday);
  return localDateKey(start);
}

function monthKey(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
}

function formatGrowthValue(value, metric) {
  if (metric === "weight") return formatWeight(value);
  return `${Number(value).toFixed(1)} cm`;
}

function buildGrowthChartSvg(records, metric, period) {
  const width = 900;
  const height = 320;
  const margin = { top: 28, right: 28, bottom: 58, left: 68 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = records.map((record) => record.value);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const minimumRange = metric === "weight" ? 0.2 : 2;
  const range = Math.max(rawMax - rawMin, minimumRange);
  const padding = range * 0.18;
  const yMin = Math.max(0, rawMin - padding);
  const yMax = rawMax + padding;
  const yRange = yMax - yMin || 1;
  const color = metric === "weight" ? "#df6f7f" : "#408f87";
  const fill = metric === "weight" ? "rgba(223, 111, 127, 0.12)" : "rgba(64, 143, 135, 0.12)";
  const decimals = metric === "weight" ? 2 : 1;
  const unit = metric === "weight" ? "kg" : "cm";

  const points = records.map((record, index) => {
    const x = records.length === 1
      ? margin.left + plotWidth / 2
      : margin.left + (index / (records.length - 1)) * plotWidth;
    const y = margin.top + ((yMax - record.value) / yRange) * plotHeight;
    return { ...record, x, y };
  });

  const gridLines = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const y = margin.top + ratio * plotHeight;
    const value = yMax - ratio * yRange;
    return `
      <line class="growth-grid-line" x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}"></line>
      <text class="growth-axis-label" x="${margin.left - 12}" y="${y + 4}" text-anchor="end">${value.toFixed(decimals)}</text>
    `;
  }).join("");

  const labelIndexes = chartLabelIndexes(records.length, 6);
  const dateLabels = labelIndexes.map((index) => {
    const point = points[index];
    return `
      <text class="growth-date-label" x="${point.x}" y="${height - 22}" text-anchor="middle">${formatGrowthPeriodLabel(point.time, period)}</text>
    `;
  }).join("");

  const linePoints = points.map((point) => `${point.x},${point.y}`).join(" ");
  const areaPath = points.length > 1
    ? `M ${points[0].x} ${margin.top + plotHeight} L ${linePoints.replaceAll(",", " ")} L ${points.at(-1).x} ${margin.top + plotHeight} Z`
    : "";
  const circles = points.map((point) => `
    <circle class="growth-point" cx="${point.x}" cy="${point.y}" r="5" style="--point-color:${color}">
      <title>${formatGrowthPeriodLabel(point.time, period)} ${formatGrowthValue(point.value, metric)}</title>
    </circle>
  `).join("");

  return `
    <svg class="growth-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${metric === "weight" ? "體重" : "身高"}${growthPeriodLabel(period)}成長曲線，共 ${records.length} 個趨勢點">
      <text class="growth-unit-label" x="${margin.left}" y="16">${unit}</text>
      ${gridLines}
      ${areaPath ? `<path class="growth-area" d="${areaPath}" fill="${fill}"></path>` : ""}
      ${points.length > 1 ? `<polyline class="growth-line" points="${linePoints}" style="--line-color:${color}"></polyline>` : ""}
      ${circles}
      ${dateLabels}
    </svg>
  `;
}

function chartLabelIndexes(length, maximumLabels) {
  if (length <= maximumLabels) return Array.from({ length }, (_, index) => index);
  const indexes = new Set([0, length - 1]);
  for (let index = 1; index < maximumLabels - 1; index += 1) {
    indexes.add(Math.round((index / (maximumLabels - 1)) * (length - 1)));
  }
  return [...indexes].sort((a, b) => a - b);
}

function formatChartDate(iso) {
  return new Intl.DateTimeFormat("zh-Hant", {
    month: "numeric",
    day: "numeric",
  }).format(new Date(iso));
}

function formatGrowthPeriodLabel(iso, period) {
  const date = new Date(iso);
  if (period === "month") {
    return new Intl.DateTimeFormat("zh-Hant", {
      year: "numeric",
      month: "numeric",
    }).format(date);
  }
  if (period === "week") {
    const start = new Date(date);
    const day = start.getDay();
    const distanceFromMonday = day === 0 ? 6 : day - 1;
    start.setDate(start.getDate() - distanceFromMonday);
    return `${formatChartDate(start.toISOString())}週`;
  }
  return formatChartDate(iso);
}

function growthPeriodLabel(period) {
  return { day: "每日", week: "每週", month: "每月" }[period] || "每日";
}

function hasPee(record) {
  return record.pee === true || record.diaperKind === "尿尿" || record.diaperKind === "尿尿 + 便便";
}

function hasPoop(record) {
  return record.poop === true || record.diaperKind === "便便" || record.diaperKind === "尿尿 + 便便";
}

function describePoop(record) {
  const details = [record.poopAmount, record.poopColor].filter(Boolean);
  return details.length ? `大便 · ${details.join(" · ")}` : "大便";
}

function calculateFeedGap(feedings) {
  if (feedings.length < 2) return "尚無資料";
  const sorted = [...feedings].sort((a, b) => new Date(a.time) - new Date(b.time));
  const gaps = sorted.slice(1).map((record, index) => {
    return (new Date(record.time) - new Date(sorted[index].time)) / 60000;
  });
  const average = gaps.reduce((sum, gap) => sum + gap, 0) / gaps.length;
  return formatMinutes(Math.round(average));
}

function formatMinutes(minutes) {
  return `${Math.floor(minutes / 60)} 小時 ${minutes % 60} 分`;
}

function formatWeight(value) {
  const kilograms = Number(value);
  if (!Number.isFinite(kilograms)) return `${value} kg`;
  return `${kilograms.toFixed(3)} kg（${Math.round(kilograms * 1000)} g）`;
}

function formatDateCompact(iso) {
  return new Intl.DateTimeFormat("zh-Hant", {
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}

function renderProfile() {
  els.babyName.value = state.profile.name || "";
  els.birthDate.value = state.profile.birthDate || "";
  els.babyAge.textContent = calculateAge(state.profile.birthDate);
}

function renderAll() {
  renderDateNavigation();
  renderProfile();
  renderSummary();
  renderGrowthChart();
  renderDayTable();
  renderRecords();
}

async function saveProfile() {
  state.profile = {
    name: els.babyName.value.trim(),
    birthDate: els.birthDate.value,
  };
  try {
    const data = await apiFetch("/api/profile/", {
      method: "POST",
      body: JSON.stringify(state.profile),
    });
    state.profile = data.profile;
    renderProfile();
  } catch (error) {
    console.error(error);
  }
}

function resetForm() {
  els.recordForm.reset();
  els.recordTime.value = toDatetimeLocal();
  syncDiaperChoices();
  syncPoopFields();
}

async function loadData() {
  const data = await apiFetch("/api/bootstrap/");
  state.profile = data.profile || { ...defaultProfile };
  state.records = data.records || [];
  renderAll();
}

document.querySelectorAll(".type-tab").forEach((button) => {
  button.addEventListener("click", () => setActiveType(button.dataset.type));
});

document.querySelectorAll("[data-workspace-target]").forEach((button) => {
  button.addEventListener("click", () => setWorkspaceView(button.dataset.workspaceTarget));
});

document.querySelectorAll(".growth-metric-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.growthMetric = button.dataset.growthMetric;
    renderGrowthChart();
  });
});

document.querySelectorAll(".growth-period-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.growthPeriod = button.dataset.growthPeriod;
    renderGrowthChart();
  });
});

els.recordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await apiFetch("/api/records/", {
      method: "POST",
      body: JSON.stringify(buildRecord()),
    });
    state.records.push(data.record);
    state.selectedDate = recordDateKey(data.record.time);
    resetForm();
    setActiveType(state.activeType);
    renderAll();
  } catch (error) {
    console.error(error);
    alert("新增紀錄失敗，請稍後再試。");
  }
});

els.recordsList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete]");
  if (!button) return;
  try {
    await apiFetch(`/api/records/${button.dataset.delete}/`, { method: "DELETE" });
    state.records = state.records.filter((record) => String(record.id) !== button.dataset.delete);
    renderAll();
  } catch (error) {
    console.error(error);
    alert("刪除紀錄失敗，請稍後再試。");
  }
});

els.filterType.addEventListener("change", renderRecords);
els.selectedDate.addEventListener("change", () => {
  if (els.selectedDate.value) setSelectedDate(els.selectedDate.value);
});
els.previousDateButton.addEventListener("click", () => shiftSelectedDate(-1));
els.nextDateButton.addEventListener("click", () => shiftSelectedDate(1));
els.todayButton.addEventListener("click", () => setSelectedDate(localDateKey()));
els.babyName.addEventListener("change", saveProfile);
els.birthDate.addEventListener("change", saveProfile);
els.pee.addEventListener("change", syncDiaperChoices);
els.poop.addEventListener("change", syncPoopFields);

els.clearButton.addEventListener("click", async () => {
  const confirmed = confirm("確定要清除所有紀錄嗎？這個動作無法復原。");
  if (!confirmed) return;
  try {
    await apiFetch("/api/records/", { method: "DELETE" });
    state.records = [];
    renderAll();
  } catch (error) {
    console.error(error);
    alert("清除紀錄失敗，請稍後再試。");
  }
});

els.exportButton.addEventListener("click", () => {
  const payload = JSON.stringify({ profile: state.profile, records: state.records }, null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `baby-records-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

function syncPoopFields() {
  syncDiaperChoices();
  const enabled = els.poop.checked;
  [els.poopAmount, els.poopColor].forEach((select) => {
    select.disabled = !enabled;
    if (!enabled) select.value = "";
    select.closest(".poop-detail")?.classList.toggle("is-disabled", !enabled);
  });
}

function syncDiaperChoices() {
  [els.pee, els.poop].forEach((input) => {
    input.closest(".check-field")?.classList.toggle("is-checked", input.checked);
  });
}

els.todayLabel.textContent = formatDateLong();
els.selectedDate.value = state.selectedDate;
els.recordTime.value = toDatetimeLocal();
setActiveType(state.activeType);
setWorkspaceView(state.workspaceView);
syncDiaperChoices();
syncPoopFields();
loadData().catch((error) => {
  console.error(error);
  renderAll();
});

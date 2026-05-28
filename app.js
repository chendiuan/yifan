const storageKey = "yifan-baby-records";
const profileKey = "yifan-baby-profile";
const defaultProfile = { name: "依杋", birthDate: "2026-05-18" };

const typeLabels = {
  feeding: "餵食",
  sleep: "睡眠",
  diaper: "尿布",
  health: "健康",
  growth: "成長",
  note: "備註",
};

const typeShort = {
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

const state = {
  activeType: "feeding",
  records: readJson(storageKey, []),
  profile: normalizeProfile(readJson(profileKey, defaultProfile)),
};

const els = {
  todayLabel: document.querySelector("#todayLabel"),
  babyName: document.querySelector("#babyName"),
  birthDate: document.querySelector("#birthDate"),
  babyAge: document.querySelector("#babyAge"),
  feedCount: document.querySelector("#feedCount"),
  sleepTotal: document.querySelector("#sleepTotal"),
  peeCount: document.querySelector("#peeCount"),
  poopCount: document.querySelector("#poopCount"),
  lastRecord: document.querySelector("#lastRecord"),
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
  poop: document.querySelector("#poop"),
  pee: document.querySelector("#pee"),
  poopAmount: document.querySelector("#poopAmount"),
  poopColor: document.querySelector("#poopColor"),
};

function readJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function normalizeProfile(profile) {
  if (!profile || !profile.name || profile.name === "YiFan" || profile.name === "陳依枋") {
    saveJson(profileKey, defaultProfile);
    return { ...defaultProfile };
  }
  return {
    name: profile.name,
    birthDate: profile.birthDate || defaultProfile.birthDate,
  };
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function toDatetimeLocal(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function isToday(iso) {
  const date = new Date(iso);
  const now = new Date();
  return date.toDateString() === now.toDateString();
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
    id: crypto.randomUUID(),
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
    record.pee = document.querySelector("#pee").checked;
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
    return [record.weight && `${record.weight} kg`, record.height && `${record.height} cm`].filter(Boolean).join(" · ") || "成長紀錄";
  }
  return "一般備註";
}

function renderRecords() {
  const filter = els.filterType.value;
  const records = state.records
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
          <div class="record-badge">${iconSvg(typeShort[record.type])}</div>
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
  const todayRecords = state.records
    .filter((record) => isToday(record.time))
    .sort((a, b) => new Date(a.time) - new Date(b.time));

  const columns = ["feeding", "sleep", "pee", "poop", "health", "growth", "note"];
  const rows = Array.from({ length: 24 }, (_, hour) => {
    const cells = columns
      .map((type) => {
        const records = todayRecords.filter((record) => {
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
              <span class="chip-line">${iconSvg(columnIcons[columnType] || typeShort[record.type])}
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
  return value.replace(/[&<>"']/g, (char) => {
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
  const todayRecords = state.records.filter((record) => isToday(record.time));
  const feedings = todayRecords.filter((record) => record.type === "feeding");
  const sleeps = todayRecords.filter((record) => record.type === "sleep");
  const diapers = todayRecords.filter((record) => record.type === "diaper");
  const health = state.records.filter((record) => record.type === "health" && record.temperature);

  const sleepMinutes = sleeps.reduce((sum, record) => sum + Number(record.sleepMinutes || 0), 0);
  const longestSleep = sleeps.reduce((max, record) => Math.max(max, Number(record.sleepMinutes || 0)), 0);
  const lastRecord = [...state.records].sort((a, b) => new Date(b.time) - new Date(a.time))[0];

  els.feedCount.textContent = `${feedings.length} 次`;
  els.sleepTotal.textContent = `${(sleepMinutes / 60).toFixed(1)} 小時`;
  els.peeCount.textContent = `${diapers.filter(hasPee).length} 次`;
  els.poopCount.textContent = `${diapers.filter(hasPoop).length} 次`;
  els.lastRecord.textContent = lastRecord ? `${typeLabels[lastRecord.type]} ${formatTime(lastRecord.time)}` : "無";
  els.longestSleep.textContent = longestSleep ? formatMinutes(longestSleep) : "尚無資料";
  els.latestTemp.textContent = health.length ? `${health.sort((a, b) => new Date(b.time) - new Date(a.time))[0].temperature} °C` : "尚無資料";
  els.feedGap.textContent = calculateFeedGap(feedings);
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

function renderProfile() {
  els.babyName.value = state.profile.name || "";
  els.birthDate.value = state.profile.birthDate || "";
  els.babyAge.textContent = calculateAge(state.profile.birthDate);
}

function renderAll() {
  renderProfile();
  renderSummary();
  renderDayTable();
  renderRecords();
}

function saveProfile() {
  state.profile = {
    name: els.babyName.value.trim(),
    birthDate: els.birthDate.value,
  };
  saveJson(profileKey, state.profile);
  renderProfile();
}

function resetForm() {
  els.recordForm.reset();
  els.recordTime.value = toDatetimeLocal();
  syncDiaperChoices();
  syncPoopFields();
}

document.querySelectorAll(".type-tab").forEach((button) => {
  button.addEventListener("click", () => setActiveType(button.dataset.type));
});

els.recordForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state.records.push(buildRecord());
  saveJson(storageKey, state.records);
  resetForm();
  setActiveType(state.activeType);
  renderAll();
});

els.recordsList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-delete]");
  if (!button) return;
  state.records = state.records.filter((record) => record.id !== button.dataset.delete);
  saveJson(storageKey, state.records);
  renderAll();
});

els.filterType.addEventListener("change", renderRecords);
els.babyName.addEventListener("input", saveProfile);
els.birthDate.addEventListener("change", saveProfile);
els.pee.addEventListener("change", syncDiaperChoices);
els.poop.addEventListener("change", syncPoopFields);

els.clearButton.addEventListener("click", () => {
  const confirmed = confirm("確定要清除所有本機紀錄嗎？這個動作無法復原。");
  if (!confirmed) return;
  state.records = [];
  saveJson(storageKey, state.records);
  renderAll();
});

els.exportButton.addEventListener("click", () => {
  const payload = JSON.stringify({ profile: state.profile, records: state.records }, null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `yifan-baby-records-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

els.todayLabel.textContent = formatDateLong();
els.recordTime.value = toDatetimeLocal();
setActiveType(state.activeType);
syncDiaperChoices();
syncPoopFields();
renderAll();

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

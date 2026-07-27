const viewer = document.getElementById('viewer');
const emptyState = document.getElementById('empty-state');
const navBtns = document.querySelectorAll('.nav-btn');
const historySelect = document.getElementById('history-select');
const indexList = document.getElementById('index-list');

const today = new Date().toLocaleDateString('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit'
}).replace(/\//g, '-');

let historyDates = [];

function setNav(mode) {
  navBtns.forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
}

function loadDate(date) {
  viewer.style.display = 'block';
  emptyState.style.display = 'none';
  viewer.src = 'history/briefing_' + date + '.html';
}

function showToday() {
  setNav('today');
  historySelect.style.display = 'none';

  if (historyDates.includes(today)) {
    loadDate(today);
    return;
  }

  // 若今天尚未生成，则显示最新历史日报
  if (historyDates.length > 0) {
    historySelect.value = historyDates[0];
    showHistory();
    return;
  }

  viewer.style.display = 'none';
  emptyState.style.display = 'block';
}

function showHistory() {
  setNav('history');
  historySelect.style.display = 'block';
  const date = historySelect.value;
  if (date) loadDate(date);
}

function buildHistorySelect() {
  historySelect.innerHTML = historyDates
    .map(d => '<option value="' + d + '">' + d + '</option>')
    .join('');
}

function buildIndex() {
  try {
    const doc = viewer.contentDocument || (viewer.contentWindow && viewer.contentWindow.document);
    if (!doc) return;
    const sections = doc.querySelectorAll('.competitor');
    indexList.innerHTML = '';
    if (sections.length === 0) {
      indexList.textContent = '无数据';
      return;
    }
    sections.forEach(sec => {
      const h2 = sec.querySelector('h2');
      const name = h2 ? h2.textContent.trim() : sec.id;
      const btn = document.createElement('button');
      btn.className = 'index-btn';
      btn.textContent = name;
      btn.addEventListener('click', () => {
        const target = doc.getElementById(sec.id);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      indexList.appendChild(btn);
    });
  } catch (e) {
    indexList.textContent = '无法读取索引';
  }
}

viewer.addEventListener('load', buildIndex);

navBtns.forEach(b => b.addEventListener('click', () => {
  if (b.dataset.mode === 'today') showToday();
  else showHistory();
}));

historySelect.addEventListener('change', showHistory);

async function init() {
  // 优先使用页面内嵌的日期作为兜底
  const dataEl = document.getElementById('history-data');
  if (dataEl && dataEl.dataset.dates) {
    try {
      historyDates = JSON.parse(dataEl.dataset.dates);
    } catch (e) {
      historyDates = [];
    }
  }

  // 尝试读取 history/index.json，获取最新历史列表
  try {
    const resp = await fetch('history/index.json', { cache: 'no-store' });
    if (resp.ok) {
      const list = await resp.json();
      if (Array.isArray(list) && list.length > 0) {
        historyDates = list;
      }
    }
  } catch (e) {
    console.log('[viewer] 读取 history/index.json 失败，使用页面内嵌数据', e);
  }

  buildHistorySelect();

  if (historyDates.length === 0) {
    viewer.style.display = 'none';
    emptyState.style.display = 'block';
  } else if (historyDates.includes(today)) {
    showToday();
  } else {
    historySelect.value = historyDates[0];
    showHistory();
  }
}

init();

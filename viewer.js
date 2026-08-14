const PAGES_BASE = 'https://dyingyogurt.github.io/competitor_briefing';

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
const useLocal = ['chrome-extension:', 'file:'].includes(location.protocol);

function resolvePath(relativePath) {
  if (useLocal) {
    return relativePath;
  }
  return PAGES_BASE + '/' + relativePath;
}

function setNav(mode) {
  navBtns.forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
}

function loadDate(date) {
  viewer.style.display = 'block';
  emptyState.style.display = 'none';
  viewer.src = resolvePath('history/briefing_' + date + '.html');
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
    const win = viewer.contentWindow;
    if (!doc || !win) return;
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
      btn.dataset.target = sec.id;
      btn.addEventListener('click', () => {
        const target = doc.getElementById(sec.id);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      indexList.appendChild(btn);
    });

    // 滚动时高亮当前游戏
    const updateActive = () => {
      const scrollTop = win.scrollY || doc.documentElement.scrollTop || 0;
      const offset = 24; // 顶部留一点缓冲
      let activeId = '';
      for (const sec of sections) {
        if (sec.offsetTop >= scrollTop + offset) {
          activeId = sec.id;
          break;
        }
      }
      if (!activeId && sections.length > 0) {
        activeId = sections[sections.length - 1].id;
      }
      indexList.querySelectorAll('.index-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.target === activeId);
      });
    };

    win.removeEventListener('scroll', updateActive);
    win.addEventListener('scroll', updateActive, { passive: true });
    updateActive();
  } catch (e) {
    // Pages 站点跨域时无法读取 iframe 内容DOM，这是正常现象
    indexList.textContent = '线上简报不支持索引';
  }
}

viewer.addEventListener('load', buildIndex);

navBtns.forEach(b => b.addEventListener('click', () => {
  if (b.dataset.mode === 'today') showToday();
  else showHistory();
}));

historySelect.addEventListener('change', showHistory);

async function fetchIndex() {
  // 先尝试读取本地文件（扩展自带的）
  try {
    const resp = await fetch('history/index.json', { cache: 'no-store' });
    if (resp.ok) {
      const list = await resp.json();
      if (Array.isArray(list) && list.length > 0) {
        return list;
      }
    }
  } catch (e) {
    console.log('[viewer] 本地 index.json 读取失败', e);
  }

  // 兜底：从 GitHub Pages 读取（通过 background.js 代理，避免 CORS）
  try {
    const resp = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: 'fetchUrl', url: PAGES_BASE + '/history/index.json' },
        (result) => {
          if (chrome.runtime.lastError || !result || !result.ok) {
            reject(new Error(chrome.runtime.lastError?.message || 'fetch failed'));
          } else {
            resolve(result);
          }
        }
      );
    });
    const list = JSON.parse(resp.body);
    if (Array.isArray(list) && list.length > 0) {
      return list;
    }
  } catch (e) {
    console.log('[viewer] Pages 读取也失败', e);
  }

  return null;
}

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

  const list = await fetchIndex();
  if (list) {
    historyDates = list;
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

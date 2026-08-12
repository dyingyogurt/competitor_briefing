const PAGES_BASE = 'https://dyingyogurt.github.io/competitor_briefing';
const BRIEFING_URL = chrome.runtime.getURL('briefing.html');
const STATUS_URL = `${PAGES_BASE}/last_run_status.json`;
const SCHEDULE_BAT_PATH = 'C:\\Users\\dengyufan\\Documents\\Default Project\\competitor_briefing\\定时任务-创建.bat';

function showMsg(text) {
  const msgEl = document.getElementById('msg');
  msgEl.textContent = text;
  setTimeout(() => { msgEl.textContent = ''; }, 3000);
}

function closePopup() {
  window.close();
}

function getTodayStr() {
  return new Date().toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).replace(/\//g, '-');
}

function fmtDateTime(isoLike) {
  if (!isoLike) return '--';
  const d = new Date(isoLike.replace(/-/g, '/'));
  if (isNaN(d.getTime())) return isoLike;
  return d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

async function fetchJsonLocal(url) {
  const resp = await fetch(url, { cache: 'no-store' });
  if (!resp.ok) throw new Error('status not ok');
  return resp.json();
}

async function fetchJsonOnline(url) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: 'fetchUrl', url }, (res) => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (!res || !res.ok) return reject(new Error(res?.error || 'network'));
      try {
        resolve(JSON.parse(res.body));
      } catch (e) {
        reject(e);
      }
    });
  });
}

async function loadStatus() {
  const dot = document.getElementById('status-dot');
  const main = document.querySelector('.status-main');
  const text = document.getElementById('status-text');
  const meta = document.getElementById('status-meta');
  const today = getTodayStr();

  let status = null;
  let source = '';

  // 1) 先读线上最新状态（因为 CI 跑的才是最权威状态）
  try {
    status = await fetchJsonOnline(STATUS_URL);
    source = '线上';
  } catch (e) {
    console.log('[popup] 线上状态获取失败，尝试本地：', e.message);
  }

  // 2) 再读本地，若本地更新则用它
  try {
    const local = await fetchJsonLocal('last_run_status.json');
    if (!status || (local.checked_at && local.checked_at > status.checked_at)) {
      status = local;
      source = '本地';
    }
  } catch (e) {
    console.log('[popup] 本地状态获取失败：', e.message);
  }

  if (!status) {
    dot.className = 'status-dot';
    main.className = 'status-main';
    text.textContent = '尚未检测到生成记录';
    meta.innerHTML = '<div class="meta-row"><span class="meta-label">可运行</span><span class="meta-value">双击运行.bat</span></div>';
    return;
  }

  const isToday = status.date === today;
  const isSuccess = status.success !== false;

  if (isSuccess && isToday) {
    dot.className = 'status-dot success';
    main.className = 'status-main success';
    text.textContent = '今日简报已生成';
  } else if (isSuccess) {
    dot.className = 'status-dot';
    main.className = 'status-main';
    text.textContent = `最近生成：${status.date}`;
  } else {
    dot.className = 'status-dot error';
    main.className = 'status-main error';
    text.textContent = `上次生成失败：${status.message || ''}`;
  }

  const rows = [];
  rows.push(['来源', source]);
  rows.push(['生成时间', fmtDateTime(status.checked_at)]);
  rows.push(['数据日期', status.date || '--']);
  if (typeof status.competitors_count === 'number') {
    rows.push(['竞品数量', `${status.competitors_count} 个`]);
  }
  if (typeof status.history_days === 'number') {
    rows.push(['趋势历史', `${status.history_days} 天`]);
  }

  meta.innerHTML = rows.map(([label, value]) => {
    const safeValue = String(value).replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<div class="meta-row"><span class="meta-label">${label}</span><span class="meta-value">${safeValue}</span></div>`;
  }).join('');
}

document.getElementById('view-btn').addEventListener('click', () => {
  chrome.tabs.create({ url: BRIEFING_URL }, () => {
    if (chrome.runtime.lastError) {
      console.error('[popup] 打开日报失败：', chrome.runtime.lastError.message);
    }
    closePopup();
  });
});

document.getElementById('usage-btn').addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('usage.html') }, () => {
    if (chrome.runtime.lastError) {
      console.error('[popup] 打开使用说明失败：', chrome.runtime.lastError.message);
    }
    closePopup();
  });
});

document.getElementById('refresh-btn').addEventListener('click', () => {
  chrome.tabs.query({ url: BRIEFING_URL + '*' }, (tabs) => {
    tabs.forEach((tab) => {
      try {
        chrome.tabs.reload(tab.id, { bypassCache: true });
      } catch (err) {
        console.error('[popup] 刷新标签页失败：', err);
      }
    });
    showMsg('简报已刷新');
    setTimeout(closePopup, 600);
  });
});

document.getElementById('export-btn').addEventListener('click', () => {
  const today = getTodayStr();
  const fileUrl = chrome.runtime.getURL(`history/briefing_${today}.html`);
  chrome.downloads.download({
    url: fileUrl,
    filename: `竞品日报_${today}.html`,
    saveAs: true,
  }, (downloadId) => {
    if (chrome.runtime.lastError) {
      showMsg('导出失败：' + chrome.runtime.lastError.message);
    } else {
      showMsg('导出已开始');
      setTimeout(closePopup, 500);
    }
  });
});

document.getElementById('schedule-toggle').addEventListener('click', function () {
  const steps = document.getElementById('schedule-steps');
  const isCollapsed = steps.classList.toggle('collapsed');
  this.textContent = isCollapsed ? '展开操作步骤 ▼' : '收起 ▲';
});

document.getElementById('copy-path-btn').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(SCHEDULE_BAT_PATH);
    showMsg('路径已复制到剪贴板');
  } catch (err) {
    showMsg('复制失败：' + err.message);
  }
});

loadStatus();

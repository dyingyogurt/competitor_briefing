const PAGES_BASE = 'https://dyingyogurt.github.io/competitor_briefing';
const BRIEFING_URL = chrome.runtime.getURL('briefing.html');
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

async function loadStatus() {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  const today = getTodayStr();

  async function tryFetch(url) {
    const resp = await fetch(url, { cache: 'no-store' });
    if (!resp.ok) throw new Error('status not ok');
    return resp.json();
  }

  let status;
  try {
    status = await tryFetch('last_run_status.json');
  } catch (e) {
    dot.className = 'status-dot';
    text.className = 'status-text';
    text.textContent = '尚未检测到生成记录';
    return;
  }

  if (status.success && status.date === today) {
    dot.className = 'status-dot success';
    text.className = 'status-text success';
    text.textContent = `今日简报已生成 · ${status.checked_at}`;
  } else if (status.success) {
    dot.className = 'status-dot';
    text.className = 'status-text';
    text.textContent = `最近生成：${status.date} · ${status.message}`;
  } else {
    dot.className = 'status-dot error';
    text.className = 'status-text error';
    text.textContent = `上次生成失败：${status.message}`;
  }
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
  // 刷新所有已打开的简报标签页，让它重新加载最新日报
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
  const fileUrl = `${PAGES_BASE}/history/briefing_${today}.html`;
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

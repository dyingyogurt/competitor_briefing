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

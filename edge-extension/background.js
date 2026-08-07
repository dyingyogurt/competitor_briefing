const NOTIFICATION_ID = 'daily-briefing';
const BRIEFING_URL = chrome.runtime.getURL('briefing.html');

// 同一个浏览器运行期间，最多只弹一次通知
let hasNotified = false;

function openBriefingTab() {
  chrome.tabs.create({ url: BRIEFING_URL });
}

function showBriefingNotification(force = false) {
  if (!force && hasNotified) {
    return;
  }

  chrome.notifications.getPermissionLevel((level) => {
    if (level !== 'granted') {
      console.log('[竞品日报] 没有通知权限，无法弹出通知。请在系统设置中允许 Edge 发送通知。');
      return;
    }

    // 注意：Windows 平台不支持通知按钮，因此移除 buttons，统一通过点击通知打开日报
    chrome.notifications.create(NOTIFICATION_ID, {
      type: 'basic',
      iconUrl: 'icon.png',
      title: '一将成名竞品日报',
      message: '今日简报已生成，点击查看。',
      requireInteraction: true
    }, () => {
      if (chrome.runtime.lastError) {
        console.log('[竞品日报] 通知创建失败：', chrome.runtime.lastError.message);
      } else {
        hasNotified = true;
      }
    });
  });
}

// 浏览器启动时重置标记并弹通知
chrome.runtime.onStartup.addListener(() => {
  hasNotified = false;
  showBriefingNotification(true);
});

// 扩展安装/更新后也弹一次，方便测试
chrome.runtime.onInstalled.addListener(() => {
  hasNotified = false;
  showBriefingNotification(true);
});

// 当用户关闭所有窗口后再次打开第一个窗口时补弹（如果还没弹过）
chrome.windows.onCreated.addListener(() => {
  showBriefingNotification(false);
});

// 点击通知打开日报
chrome.notifications.onClicked.addListener((notificationId) => {
  if (notificationId === NOTIFICATION_ID) {
    openBriefingTab();
    chrome.notifications.clear(notificationId);
  }
});

// 注意：插件已配置 default_popup，点击图标会显示 popup.html，
// 因此 chrome.action.onClicked 不会触发。

// 代理 fetch 请求，绕过 popup/viewer 中的 CORS 限制
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'fetchUrl' && msg.url) {
    fetch(msg.url, { cache: 'no-store' })
      .then(resp => resp.text().then(body => sendResponse({ ok: resp.ok, status: resp.status, body })))
      .catch(err => sendResponse({ ok: false, status: 0, body: '', error: err.message }));
    return true; // 保持消息通道打开，等待异步响应
  }
});

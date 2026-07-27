# 三国杀一将成名竞品日报

自动抓取 App Store 数据，并补充 Bilibili 玩家舆情，每天自动生成一份竞品日报，通过 Edge 浏览器扩展查看。

## 一、核心功能

### 1. 自动采集 App Store 数据

每天自动抓取以下信息：

- **版本更新**：当前版本号、更新日期、开发商、更新说明；
- **iOS 榜单排名**：总畅销榜 / 总免费榜 / 游戏畅销榜 / 游戏免费榜 Top100 排名；
- **App Store 评论**：近期评论样本、评分分布、负面关键词（注：中国区 RSS 评论接口目前已不稳定，可能无数据）。

当前监控的竞品：

| 产品 | 说明 |
|------|------|
| 三国杀一将成名 | 本产品（核心关注对象） |
| 名将杀 | 直接竞品 |
| 英雄杀 | 腾讯系卡牌竞品 |
| 三国：百将牌 | 新兴卡牌竞品 |

### 2. Bilibili 玩家舆情补充

由于 App Store 评论接口经常无数据，脚本会自动搜索 B 站相关视频，抓取热门评论，并做简单情感统计：

- 正面 / 负面 / 中性 占比；
- 负面高频词；
- 热门评论样本。

目前仅对「三国杀一将成名」开启，其他竞品可在 `config.py` 中配置 `bilibili_keyword`。

### 3. 人工补充字段

打开 `manual_overrides.json`，可手动补充以下信息，脚本会自动合并进日报：

| 字段 | 含义 |
|------|------|
| `taptap_rating` | TapTap 评分 |
| `taptap_heat` | TapTap 热度 / 关注数 / 论坛活跃度 |
| `marketing` | 市场动向（联动、代言、投放） |
| `events` | 重点活动 |
| `notes` | 其他备注 / 热度估算 / 精确排名等 |

### 4. Edge 浏览器扩展

安装扩展后：

- **每天早上第一次打开 Edge**：右上角弹出通知，点击后才打开简报；
- **点击工具栏图标**：随时打开 popup，查看今日简报或使用说明；
- **新标签页保持正常**：不会被替换成日报页面。

### 5. 每日自动生成

通过 Windows 计划任务，每天固定时间自动生成简报，无需手动操作。

- 默认时间：每天 **10:00**；
- 支持**错过补跑**：如果生成时间电脑关机，开机后会自动补跑一次；
- 运行日志保存在 `task.log`。

---

## 二、产物说明

运行脚本后会生成两个产物：

| 产物 | 路径 | 用途 |
|------|------|------|
| Markdown 简报 | `output/daily_briefing_YYYY-MM-DD.md` | 适合存档、转发、二次编辑 |
| HTML 简报 | `edge-extension/briefing.html` | 供 Edge 扩展读取和展示 |

---

## 三、快速开始

### 环境要求

- **Windows 电脑**（任务计划程序为 Windows 专属）；
- **Python 3.x**，安装时务必勾选 **「Add Python to PATH」**；
- **Microsoft Edge 浏览器**；
- 能访问 `itunes.apple.com` 和 `api.bilibili.com` 的网络。

Pyhton 下载地址：https://www.python.org/downloads/

### 第一步：生成一次简报

进入项目文件夹，双击运行：

```text
双击运行.bat
```

等待脚本执行完毕，会生成：

```text
output/daily_briefing_2026-07-22.md
edge-extension/briefing.html
```

### 第二步：安装 Edge 扩展

1. 打开 Edge，地址栏输入：
   ```text
   edge://extensions/
   ```
2. 打开左下角 **「开发人员模式」**；
3. 点击 **「加载解压缩的扩展」**；
4. 选择项目中的 `edge-extension` 文件夹；
5. 安装完成后，Edge 工具栏会出现一个蓝色「日」字图标。

### 第三步：查看简报

点击工具栏的蓝色「日」字图标，在弹出面板中选择：

- **「查看今日简报」**：在新标签页打开今日 HTML 简报；
- **「查看使用说明」**：打开扩展使用说明，包含数据限制、手动生成和定时任务设置方法。

---

## 四、设置每日自动生成

### 推荐方式：`setup_for_team.bat` 一键安装

1. 打开 `setup_for_team.bat`；
2. 如需修改生成时间，改第 14 行：
   ```batch
   set "triggerTime=10:00"
   ```
   例如改成每天 15:30：
   ```batch
   set "triggerTime=15:30"
   ```
3. 保存文件；
4. 右键 `setup_for_team.bat` → **「以管理员身份运行」**；
5. 看到 `Setup completed successfully` 即完成。

这个脚本会自动完成：

- 检测 Python 路径；
- 生成带完整 Python 路径的 `run_task.bat`；
- 创建每天定时生成简报的计划任务；
- 开启「错过补跑」功能。

### 验证任务是否创建成功

按 `Win + R`，输入：

```text
taskschd.msc
```

回车，在「任务计划程序库」中找到 `competitor-briefing-daily`，即表示创建成功。

右键该任务 →「属性」→「设置」，确认勾选了：

```text
☑ 如果过了计划开始时间，任务还没有启动，则立即启动任务
```

这样就开启了错过补跑。

### 手动运行测试

在 `taskschd.msc` 中，右键 `competitor-briefing-daily` →「运行」，等待 10~20 秒后，检查：

- `edge-extension\briefing.html` 修改时间是否更新；
- `task.log` 是否有新的运行记录。

### 删除定时任务

右键 `定时任务-删除.bat` → **「以管理员身份运行」**。

---

## 五、团队部署流程

把项目文件夹复制给项目组成员，每个人按以下步骤操作一次：

1. **安装 Python**：从官网下载安装，勾选 Add to PATH；
2. **修改时间（可选）**：打开 `setup_for_team.bat`，把 `triggerTime` 改成组内约定的时间；
3. **一键安装**：右键 `setup_for_team.bat` → 以管理员身份运行；
4. **安装 Edge 扩展**：按上文「安装 Edge 扩展」步骤操作；
5. **验证**：点击扩展图标，查看今日简报。

---

## 六、数据说明与限制

### 1. iOS 榜单仅支持 Top100

Apple 公开 RSS 榜单接口最多返回前 100 名。如果竞品未进入 Top100，会显示：

> 未进入 Top100（Apple 公开 RSS 仅提供前 100 名）

如需精确排名，需采购七麦、Sensor Tower 等付费数据接口。

### 2. App Store 评论接口不稳定

中国区 App Store 的 RSS 评论接口目前经常返回空数据。这不是代码问题，而是数据源本身无数据。

已接入 Bilibili 评论作为补充，同时建议在 `manual_overrides.json` 中人工补充 TapTap / 贴吧 / 微博舆情。

### 3. Bilibili 舆情仅供参考

B 站评论是热门评论采样，覆盖范围有限，适合观察玩家情绪和讨论焦点，不适合当作完整舆情数据。

---

## 七、目录结构

```
competitor_briefing/
├── config.py                   # 竞品配置（App Store ID、Bilibili 关键词）
├── collector.py                # App Store 自动采集逻辑
├── sentiment_collector.py      # Bilibili 舆情补充采集
├── formatter.py                # Markdown / HTML 简报生成
├── main.py                     # 每日入口
├── history.py                  # 历史快照与异动对比
├── push.py                     # （预留）办公软件推送
├── manual_overrides.json       # 人工补充字段
├── requirements.txt            # 当前无需第三方包
├── output/                     # 生成的 Markdown 文件
├── edge-extension/             # Edge 浏览器扩展
│   ├── manifest.json
│   ├── background.js           # 浏览器启动通知 + 图标点击
│   ├── icon.png                # 扩展图标
│   ├── popup.html              # 扩展弹出面板
│   ├── popup.css
│   ├── popup.js
│   ├── usage.html              # 扩展内置的使用说明页
│   └── briefing.html           # 由 Python 生成（不要手动编辑）
├── 双击运行.bat                # 一键生成简报
├── 生成并查看.bat              # 一键生成并用 Edge 查看
├── setup_for_team.bat          # 团队一键安装：检测 Python + 创建计划任务
├── create_task.ps1             # setup_for_team.bat 内部调用，创建计划任务
├── run_task.bat                # 供计划任务调用的启动脚本（含日志）
├── 定时任务-创建.bat           # 手动创建计划任务
└── 定时任务-删除.bat           # 删除计划任务
```

---

## 八、常见问题

**Q：运行脚本时报 `ssl` 或 `timeout`？**  
A：检查网络能否访问 `itunes.apple.com`。部分企业网络需配置代理，可在 `collector.py` 中添加 `urllib.request.ProxyHandler`。

**Q：榜单都是 Top100 外怎么办？**  
A：Apple 公开榜单只返回前 100 名。脚本会明确提示。精确排名需付费 API。

**Q：App Store 评论没有数据？**  
A：中国区 RSS 评论接口目前已不稳定。已在日报中提示，可用 Bilibili 舆情和 `manual_overrides.json` 人工补充。

**Q：打开浏览器没有弹出通知？**  
A：
1. 确认扩展已重新加载；
2. 检查 Windows 通知设置中是否允许 Edge 发送通知；
3. 检查 Edge 设置 → Cookie 和网站权限 → 通知，是否允许 Edge 通知。

**Q：点击扩展图标没反应？**  
A：确认已经运行过 `python main.py` 生成了 `briefing.html`；确认扩展已加载且未被禁用。

**Q：定时任务到了时间不运行？**  
A：先手动在 `taskschd.msc` 中右键任务 →「运行」，看能否成功。再检查 `task.log` 中的报错信息。

**Q：错过时间后开机没补跑？**  
A：确认任务属性「设置」中勾选了「如果过了计划开始时间，任务还没有启动，则立即启动任务」。如果没有，删除任务后用新版 `setup_for_team.bat` 重新创建。

---

## 九、后续可扩展方向

- 接入七麦 / Sensor Tower 付费 API，获取精确排名和完整评论；
- 接入 TapTap 评分/热度/论坛（需解决反爬）；
- 接入百度指数 / 微信指数，作为热度趋势参考；
- 接入 AI 总结，自动生成每日摘要和启示。

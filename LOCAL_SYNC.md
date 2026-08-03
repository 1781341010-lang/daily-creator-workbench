# 本机定时抓取 1688 / alibaba 真实榜单（电脑线材）

本文件教你在本机每日定时运行 `scrape_real.py`，把 **1688.com 与 alibaba.com** 上「电脑线材」类目的
**真实销量 TOP10 + 真实新品 TOP10**（含**真实商品主图**与**真实商品链接**）写入 `data.real.json` 覆盖层，App 自动优先显示，横幅变「✅ 实时数据」。

> 为什么必须本机跑：1688 与 alibaba 都封锁机器人——1688 连请求都被拦成验证页，alibaba 商品是 JS 渲染的。
> 只有**你本机（中国 IP + 已登录的浏览器 Cookie）**用无头浏览器才能拿到真实主图与真实链接。

---

## 0. 一次性准备

1. 安装依赖（只需一次）：
   ```bash
   pip install playwright beautifulsoup4
   playwright install chromium
   ```
2. 导出两个平台的登录 Cookie（Netscape/curl 格式）：
   - 浏览器装插件 **EditThisCookie** → 分别打开 **1688.com** 和 **alibaba.com** 并登录；
   - 各导出为 Netscape 格式 → 存成 `cookies_1688.txt` 与 `cookies_alibaba.txt`（脚本同目录）。
   - 两个文件都已被 `.gitignore` 忽略，不会误提交。
   - 也支持环境变量：`A1688_COOKIE="name=value; ..."` 与 `ALIBABA_COOKIE="name=value; ..."`。
3. 先手动跑一次，确认能抓到真实数据：
   ```bash
   python scrape_real.py
   ```
   成功会打印 `✅ 1688 电脑线材：销量 X / 新品 Y` 与 `✅ alibaba 电脑线材：...`，并写 `data.real.json`。

> 排错：若提示「解析到的商品过少」，多半是 Cookie 失效或被验证页拦截。设 `REAL_DEBUG=1` 重跑，
> 会把渲染后的 HTML 存到 `/tmp/1688_*.html`、`/tmp/alibaba_*.html`，把这两个文件发我即可适配选择器。

---

## 1. 可选：推送到 Gist 直供 App（免手动提交仓库）

设一个**有 `gist` 权限的 GitHub Token** 环境变量即可：
```bash
export GIST_TOKEN="ghp_xxxxxxxxxxxx"     # 有 gist 权限的 Token
export GIST_REAL_ID=""                     # 首次留空，脚本会新建并告诉你 ID；之后填回以便更新同一份
```
- 首次运行会新建一个**私有 Gist**并打印 raw 链接，把该链接填进 App「设置 → 真实数据 Gist」即可。
- 不配 `GIST_TOKEN` 也完全可行：脚本会把 `data.real.json` + `prodimg/` 自动 `git commit & push` 到仓库，GitHub Pages 同源直读（推荐，更简单）。

---

## 2. 定时任务（每日 14:00 北京时间 = 06:00 UTC）

### 方案 A：Linux / macOS 用 cron（推荐）
```bash
crontab -e
```
加入（每日 06:00 UTC = 北京 14:00；路径换成你的仓库目录）：
```cron
# 移动端创作工作台：每日 14:00(北京) 抓取 1688+alibaba 电脑线材真实榜单并发布
0 6 * * * cd /path/to/workspace && /usr/bin/python3 scrape_real.py >> /tmp/real_sync.log 2>&1
```

### 方案 B：macOS 用 launchd
新建 `~/Library/LaunchAgents/com.wb.realSync.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>Label</key><string>com.wb.realSync</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>/path/to/workspace/scrape_real.py</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/workspace</string>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardErrorPath</key><string>/tmp/real_sync.log</string>
  <key>StandardOutPath</key><string>/tmp/real_sync.log</string>
</dict>
</plist>
```
加载：`launchctl load ~/Library/LaunchAgents/com.wb.realSync.plist`。

### 方案 C：Windows 任务计划程序
创建基本任务 → 触发器「每天」14:00 → 操作「启动程序」→ 程序 `python.exe`，参数 `scrape_real.py`，起始于 `C:\path\to\workspace`。

---

## 3. 数据如何到达 App（两种通道，任选）

| 通道 | 配置 | 优点 |
|------|------|------|
| **仓库同源**（默认推荐） | 脚本自动 `git push` `data.real.json` + `prodimg/` | 无需任何额外配置，Pages 同源直读 |
| **Gist 直供** | 设 `GIST_TOKEN`；App 填「真实数据 Gist」链接 | 不依赖仓库提交，可独立更新 |

App 加载顺序：先读基础数据（`data.json` 或你配置的 Gist）→ 再叠加 `data.real.json` 覆盖层（哪个平台有真实数据，哪个就显示「✅ 实时数据」）。
云端 Actions 只重写 `data.json`，**永不覆盖** `data.real.json`，两条通道互不打架。

> GitHub Pages 对仓库推送有 ~1 分钟 CDN 缓存，发布后稍等一两分钟再刷新 App。

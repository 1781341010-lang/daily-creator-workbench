# 每日创作台 · 移动端单文件应用

一个**单文件、无后端、数据每天自动更新**的移动端创作工作台。宝石蓝主色、圆角卡片、左侧抽屉导航，含 7 个模块。

> 部署后你的网站地址：`https://你的用户名.github.io/你的仓库名/`（手机浏览器打开，可「添加到主屏幕」）

## 七个模块
| 模块 | 内容 |
|------|------|
| 🏠 概览 | 今日焦点 + 数据概览 + 快速入口 |
| 🔤 英语练习 | 每天 10 条，含音标/标签/中文说明/例句；一键唤起「百词斩」「流利说」 |
| 📰 今日热点 | 新华财经 · 证券时报 · 财联社 · 21财经，每天实时更新 |
| 🔥 1688爆款二创 | 每天 10 热门爆款 + 10 最新下单款式，附「改编角度」（规则版参考样例） |
| 🌏 国际站新款二创 | 阿里巴巴国际站同源结构（规则版参考样例） |
| 💰 基金 | 每日 14:00 净流入资金最大榜 |
| 📈 股票 | 每日 14:00 净流入资金最大榜 |

## 数据从哪来（重要）

网页默认读取**同源的 `./data.json`**（即和 `index.html` 放在一起的那个文件）。

- 每天 **北京时间 8 / 14 / 20 点**，GitHub Actions 自动跑 `generate.py` 重新生成 `data.json` 并写回仓库 → 网页自动读到最新内容。
- 首次部署时若 `data.json` 还没生成，页面会回退到内置种子数据，不会空白。
- **不需要任何 Gist、不需要任何 API Key、不需要付费 AI**——纯规则生成，零成本。

> 想要「1688 / alibaba 电脑线材」**真实销量榜+新品榜（含真实主图与真实商品链接）**？这是**可选**能力：需在**本机**用已登录的浏览器 Cookie 跑 `scrape_real.py`，把真实数据写进 `data.real.json`。网页会自动优先使用真实数据（对应平台横幅变「✅ 实时数据」）。云端 Actions **只动 `data.json`，永不覆盖 `data.real.json`**，两条通道互不打架。

## 部署（三步，纯网页操作）

1. 把本仓库里的文件（含 `.github/` 目录）上传到你的 GitHub 仓库根目录。
2. 仓库 **Settings → Pages** → Source 选 `Deploy from a branch` → Branch 选 `main`（或 `master`）、目录 `/ (root)` → Save。
3. 进仓库 **Actions** 标签 → 手动 **Run workflow** 跑一次，让 `data.json` 立刻生成（之后每天定时自动跑）。

详见 **`移动端创作工作台-搭建与分享指南.md`**（给零基础朋友的图文手册）。

## 本地预览
直接双击 `index.html` 即可（用浏览器打开）。或起个静态服务：
```bash
python3 -m http.server 8000   # 打开 http://localhost:8000
```

## 自己改
- **换主色**：改 `index.html` 顶部 CSS 的 `--primary`。
- **本地试跑生成器**：
  ```bash
  NICHE_KEYWORDS="电脑3C产品,外贸热点" python3 generate.py
  # 生成 data.json 并打印统计
  ```

## 文件
```
index.html                  单文件应用（页面+样式+逻辑都在内）
generate.py                 每日数据生成脚本（规则版，电脑线材参考样例，无随机图）
data.json                   最近一次生成结果（规则版，初始种子）
.github/workflows/daily.yml GitHub Actions 定时任务（北京 8/14/20 点，自动回写 data.json）
scrape_real.py              本机爬虫（可选）：抓 1688+alibaba 电脑线材真实榜单 → data.real.json
prodimg/                    产品主图目录（规则版为空；真实爬虫下载的真实主图放这里）
apple-touch-icon.png        主屏幕图标
README.md / 移动端创作工作台-搭建与分享指南.md / LOCAL_SYNC.md / 小白图文操作指南.md  说明文档
cookies_1688.txt.example / cookies_alibaba.txt.example  导出 Cookie 示例
.gitignore                  忽略真实 Cookie 与缓存，避免误提交
```

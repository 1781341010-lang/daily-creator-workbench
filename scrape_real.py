#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实榜单抓取（1688.com + alibaba.com，仅「电脑线材」类目）
============================================================
1688 与 alibaba 都封锁机器人：
  - 1688 连初始请求都会被拦成验证页（必须登录态 + 中国 IP）。
  - alibaba 商品是 JS 动态渲染，纯静态抓不到真实商品。
因此本脚本用「无头浏览器（Playwright）+ 你浏览器里的登录 Cookie」来渲染并提取
真实商品：真实主图（下载到 prodimg/）、真实商品详情链接、销量、上架时间。

只聚焦一个类目：电脑线材（用户明确要求「电脑线材类目」真实数据）。
每组输出：销量 TOP10（按前台累计销量）+ 最新上架 TOP10（按上架时间倒序）。

用法：
  1) 装依赖： pip install playwright && playwright install chromium
  2) 导出登录 Cookie：
       - cookies_1688.txt    （Netscape 格式，1688.com 已登录）
       - cookies_alibaba.txt （Netscape 格式，alibaba.com 已登录）
     用浏览器插件 EditThisCookie 导出，或设环境变量 A1688_COOKIE / ALIBABA_COOKIE。
  3) 运行： python scrape_real.py
  4) 成功写入 data.real.json（覆盖层）；App 优先用它对规则数据做覆盖，显示「✅ 实时数据」。

可选环境变量：
  GIST_TOKEN      推送到 Gist（真实数据备份 / 直供 App，无需提交仓库）
  GIST_REAL_ID    已有 Gist 的 ID（首次留空会自动新建）
  REAL_DEBUG=1    把渲染后的 HTML 存到当前目录便于排查选择器
"""
import os, sys, re, json, datetime, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "prodimg")
COOKIE_1688 = os.path.join(BASE, "cookies_1688.txt")
COOKIE_ALIBABA = os.path.join(BASE, "cookies_alibaba.txt")

CATEGORY_CN = "电脑线材"
CATEGORY_EN = "computer cable"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ----------------------------------------------------------------------------
# Cookie 加载
# ----------------------------------------------------------------------------
def load_cookie_netscape(path):
    """读取 Netscape/curl 格式 Cookie 文件 → list[{name,value,domain,path,expiry,secure}]"""
    if not os.path.exists(path):
        return []
    pairs = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                try:
                    exp = int(parts[4]) if parts[4] not in ("", "0") else None
                except ValueError:
                    exp = None
                pairs.append({
                    "name": parts[5], "value": parts[6],
                    "domain": parts[0].lstrip("."), "path": parts[2] or "/",
                    "expiry": exp, "secure": parts[1].lower() == "true",
                })
            elif "=" in line:
                # 退化：name=value 行
                k, v = line.split("=", 1)
                pairs.append({"name": k.strip(), "value": v.strip(),
                              "domain": "", "path": "/", "expiry": None, "secure": False})
    return pairs


def load_cookies(platform):
    """返回某平台的 Cookie 列表（Netscape 文件优先，否则环境变量）。"""
    if platform == "1688":
        env = os.environ.get("A1688_COOKIE", "")
        path = COOKIE_1688
        host = "1688.com"
    else:
        env = os.environ.get("ALIBABA_COOKIE", "")
        path = COOKIE_ALIBABA
        host = "alibaba.com"
    if env:
        return [{"name": k.strip(), "value": v.strip(), "domain": host, "path": "/",
                 "expiry": None, "secure": True}
                for k, v in (kv.split("=", 1) for kv in env.split(";") if "=" in kv)]
    return load_cookie_netscape(path)


def cookies_for_host(cookies, host):
    """挑出匹配目标域的 Cookie，补上 Playwright 需要的字段。"""
    out = []
    for c in cookies:
        dom = (c.get("domain") or "").lstrip(".")
        if host in dom or dom.endswith(host) or dom == "":
            out.append({
                "name": c["name"], "value": c["value"],
                "domain": host, "path": c.get("path") or "/",
                "secure": True, "httpOnly": False,
            })
    return out


# ----------------------------------------------------------------------------
# 浏览器渲染 + 提取
# ----------------------------------------------------------------------------
def _safe(name):
    return "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in name)[:50]


def _launch():
    from playwright.sync_api import sync_playwright
    return sync_playwright


def _extract_1688(page):
    """从 1688 搜索结果页提取商品（标题/主图/链接/文本）。"""
    return page.evaluate("""() => {
      const out=[]; const seen=new Set();
      const links=[...document.querySelectorAll('a[href*="detail.1688.com"]')];
      for(const a of links){
        const href=a.href; if(!href||seen.has(href)) continue; seen.add(href);
        const card=a.closest('div.offer-item,li.offer-item,div.sm-offer-item,div.sm-offer,.offer-card')||a.parentElement;
        const title=(a.getAttribute('title')||a.innerText||'').replace(/\\s+/g,' ').trim();
        const img=card?card.querySelector('img'):null;
        const src=img?(img.getAttribute('src')||img.getAttribute('data-lazyload')||img.getAttribute('data-src')||img.src||''):'';
        const txt=card?(card.innerText||'').replace(/\\s+/g,' '):'';
        if(title && src && /alicdn|1688/.test(src)) out.push({title,href,src,txt});
      }
      return out;
    }""")


def _extract_alibaba(page):
    """从 alibaba 搜索结果页提取商品。"""
    return page.evaluate("""() => {
      const out=[]; const seen=new Set();
      const links=[...document.querySelectorAll('a[href*="/product/"]')];
      for(const a of links){
        const href=a.href; if(!href||seen.has(href)) continue; seen.add(href);
        const card=a.closest('div[class*="card"],li[class*="card"],article,.search-card')||a.parentElement;
        const title=(a.getAttribute('title')||a.innerText||'').replace(/\\s+/g,' ').trim();
        const img=card?card.querySelector('img'):null;
        let src=img?(img.getAttribute('src')||img.getAttribute('data-src')||img.getAttribute('data-lazyload')||img.src||''):'';
        const txt=card?(card.innerText||'').replace(/\\s+/g,' '):'';
        if(title && title.length>4 && src && /alicdn|alibaba/.test(src)) out.push({title,href,src,txt});
      }
      return out;
    }""")


def _parse_sales_1688(txt):
    m = re.search(r"成交\s*([\d\.]+)\s*([万]?)\s*笔", txt)
    if not m:
        m = re.search(r"([\d\.]+)\s*([万]?)\s*笔", txt)
    if not m:
        return None
    n = float(m.group(1))
    if m.group(2) == "万":
        n *= 10000
    return int(n)


def _parse_sales_alibaba(txt):
    m = re.search(r"([\d][\d,\.]*)\s*(?:\+)?\s*(?:sold|orders|transactions)", txt, re.I)
    if not m:
        return None
    try:
        return int(float(m.group(1).replace(",", "")))
    except ValueError:
        return None


def _parse_days_1688(txt):
    m = re.search(r"(\d+)\s*天前", txt)
    return int(m.group(1)) if m else None


def download_img(url, path):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.1688.com/"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) > 1500 and data[:3] == b"\xff\xd8\xff":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        sys.stderr.write("  [图下载失败] %s: %s\n" % (url[:80], e))
    return False


def scrape_platform(playwright, platform, cookies):
    """抓取单个平台的电脑线材 销量TOP10 + 新品TOP10。返回 {tracks:[...]} 或 None。"""
    host = "1688.com" if platform == "1688" else "alibaba.com"
    if platform == "1688":
        sales_url = "https://s.1688.com/k=%s.html?sortType=book_buy" % urllib.parse.quote(CATEGORY_CN)
        new_url = "https://s.1688.com/k=%s.html?sortType=publish" % urllib.parse.quote(CATEGORY_CN)
        parse_sales, parse_days = _parse_sales_1688, _parse_days_1688
        extract = _extract_1688
    else:
        sales_url = "https://www.alibaba.com/trade/search?SearchText=%s&sortType=total_tranpro_desc" % urllib.parse.quote(CATEGORY_EN)
        new_url = "https://www.alibaba.com/trade/search?SearchText=%s&sortType=date_added" % urllib.parse.quote(CATEGORY_EN)
        parse_sales, parse_days = _parse_sales_alibaba, (lambda t: None)
        extract = _extract_alibaba

    sys.stderr.write("[%s] 启动浏览器（Cookie 注入 %d 条）\n" % (platform, len(cookies)))
    # 用非无头模式：1688/alibaba 会检测无头浏览器并弹滑块验证码，
    # 弹出真实窗口让你手动过验证后再自动抓取。
    browser = playwright.chromium.launch(headless=False,
                                         args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900})
    ctx.add_cookies(cookies_for_host(cookies, host))
    page = ctx.new_page()

    def grab(url, is_new):
        sys.stderr.write("  [抓取] %s\n" % url[:90])
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # 等页面加载 + 给用户时间手动过滑块验证码（如有）
        page.wait_for_timeout(8000)
        # 检测是否出现滑块验证码：如果有"滑块"/"验证"/"拖动"等字样，提示用户手动操作
        body_text = page.evaluate("() => document.body.innerText")
        if any(kw in body_text for kw in ["滑块", "拖动", "请验证", "验证码", "captcha", "slider"]):
            sys.stderr.write("  [⚠️ 检测到验证码！请在弹出的浏览器窗口中手动完成验证（拖滑块/点按钮）...\n")
            sys.stderr.write("  [⚠️ 完成后脚本会自动继续，最多等待 120 秒...\n")
            # 等待验证码消失（商品列表出现）或超时
            for _ in range(24):  # 最多等 120 秒
                page.wait_for_timeout(5000)
                new_text = page.evaluate("() => document.body.innerText")
                if not any(kw in new_text for kw in ["滑块", "拖动", "请验证", "验证码", "captcha", "slider"]):
                    sys.stderr.write("  [✅ 验证已通过！继续抓取...\n")
                    break
            else:
                sys.stderr.write("  [⚠️ 等待验证超时，可能仍在验证页\n")
        page.wait_for_timeout(3000)  # 再等 JS 渲染商品
        if os.environ.get("REAL_DEBUG"):
            debug_path = os.path.join(BASE, "debug_%s_%s.html" % (platform, "new" if is_new else "sales"))
            open(debug_path, "w", encoding="utf-8").write(page.content())
            sys.stderr.write("  [DEBUG] 已保存页面到 %s\n" % debug_path)
        raw = extract(page)
        items = []
        seen = set()
        for r in raw:
            t = r["title"]
            if not t or t in seen:
                continue
            seen.add(t)
            u = r["href"]
            if not u.startswith("http"):
                u = "https:" + u
            fn = _safe(platform + "_" + t) + ".jpg"
            rel = "prodimg/" + fn
            lpath = os.path.join(BASE, rel)
            if not os.path.exists(lpath):
                download_img(r["src"], lpath)
            item = {
                "name": t,
                "plat": ("1688" if platform == "1688" else "阿里国际站"),
                "angle": "真实 %s 商品：点按钮跳转查看同款与实时销量/上架信息。" % ("1688" if platform == "1688" else "alibaba"),
                "tags": [CATEGORY_CN if platform == "1688" else "Computer Cable", platform.upper() if platform == "1688" else "Alibaba"],
                "img": rel if os.path.exists(lpath) else "",
                "url": u,
            }
            if is_new:
                days = parse_days(r["txt"])
                item["listedDays"] = days if days is not None else 0
                item["listedAt"] = ("%d天前" % days) if days is not None else "上新"
            else:
                item["sales"] = parse_sales(r["txt"]) or 0
            items.append(item)
            if len(items) >= 10:
                break
        return items

    try:
        sales_list = grab(sales_url, False)
        new_list = grab(new_url, True)
    finally:
        browser.close()

    if len(sales_list) < 3 and len(new_list) < 3:
        sys.stderr.write("  [%s] 解析到的商品过少（可能被验证页拦截或选择器需更新）；见 debug_%s_*.html\n" % (platform, platform))
        return None
    return {"key": "cable", "name": CATEGORY_CN, "sales": sales_list, "new": new_list}


# ----------------------------------------------------------------------------
# Gist 推送 / git 提交
# ----------------------------------------------------------------------------
def _push_to_gist(payload_obj, token, gist_id=None):
    import urllib.request
    content = json.dumps(payload_obj, ensure_ascii=False, indent=2)
    api = "https://api.github.com/gists"
    headers = {"Authorization": "token %s" % token, "Accept": "application/vnd.github+json",
               "User-Agent": "wb-scraper", "Content-Type": "application/json"}
    if gist_id:
        body = json.dumps({"files": {"data.real.json": {"content": content}}}).encode("utf-8")
        url, method = api + "/" + gist_id, "PATCH"
    else:
        body = json.dumps({"public": False, "description": "电脑线材真实榜单覆盖层（移动端创作工作台）",
                           "files": {"data.real.json": {"content": content}}}).encode("utf-8")
        url, method = api, "POST"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8", "ignore"))
        raw = j.get("files", {}).get("data.real.json", {}).get("raw_url", "")
        return (j.get("id"), raw)
    except Exception as e:
        sys.stderr.write("  [Gist 推送失败] %s\n" % e)
        return (None, None)


def _git_commit_push(files, msg):
    import subprocess
    try:
        subprocess.run(["git", "add"] + files, check=True, cwd=BASE,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        diff = subprocess.run(["git", "status", "--porcelain"] + files, cwd=BASE, capture_output=True, text=True)
        if not diff.stdout.strip():
            sys.stderr.write("  [git] 数据无变化，跳过提交。\n")
            return True
        subprocess.run(["git", "commit", "-m", msg], check=True, cwd=BASE,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "push"], check=True, cwd=BASE,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        sys.stderr.write("  [git] 已提交并推送：%s\n" % ", ".join(files))
        return True
    except Exception as e:
        sys.stderr.write("  [git 提交/推送失败，请手动推送] %s\n" % e)
        return False


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    if not load_cookies("1688") and not load_cookies("alibaba"):
        sys.stderr.write(
            "未找到 cookies_1688.txt / cookies_alibaba.txt，也未设置 A1688_COOKIE / ALIBABA_COOKIE。\n"
            "请先导出 1688.com 与 alibaba.com 的登录 Cookie（Netscape 格式）再运行本脚本。\n")
        sys.exit(2)

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        sys.stderr.write("缺少 playwright：请先 `pip install playwright && playwright install chromium`\n")
        sys.exit(3)

    overlay = {"live": True, "source": "1688+alibaba",
               "updatedAt": int(datetime.datetime.now().timestamp() * 1000), "p1688": None, "pintl": None}
    ok = False
    with sync_playwright() as pw:
        # 1688
        c1688 = load_cookies("1688")
        if c1688:
            try:
                res = scrape_platform(pw, "1688", c1688)
                if res:
                    overlay["p1688"] = {"tracks": [res]}
                    ok = True
                    sys.stderr.write("✅ 1688 电脑线材：销量 %d / 新品 %d\n" % (len(res["sales"]), len(res["new"])))
            except Exception as e:
                sys.stderr.write("  [1688 抓取失败] %s\n" % e)
        # alibaba
        cali = load_cookies("alibaba")
        if cali:
            try:
                res = scrape_platform(pw, "alibaba", cali)
                if res:
                    overlay["pintl"] = {"tracks": [res]}
                    ok = True
                    sys.stderr.write("✅ alibaba 电脑线材：销量 %d / 新品 %d\n" % (len(res["sales"]), len(res["new"])))
            except Exception as e:
                sys.stderr.write("  [alibaba 抓取失败] %s\n" % e)

    if not ok:
        sys.stderr.write("两个平台都未抓到有效数据（多半 Cookie 失效 / 被验证页拦截 / 选择器需更新）。\n"
                         "可设 REAL_DEBUG=1 重跑，把 debug_1688_*.html 与 debug_alibaba_*.html 发我以适配选择器。\n")
        sys.exit(1)

    # 写覆盖层
    real_path = os.path.join(BASE, "data.real.json")
    with open(real_path, "w", encoding="utf-8") as f:
        json.dump(overlay, f, ensure_ascii=False, indent=2)
    sys.stderr.write("✅ 真实覆盖层已写入 data.real.json\n")

    # 可选：Gist 推送
    gist_token = os.environ.get("GIST_TOKEN", "").strip()
    if gist_token:
        gid = os.environ.get("GIST_REAL_ID", "").strip() or None
        new_id, raw = _push_to_gist(overlay, gist_token, gid)
        if raw:
            sys.stderr.write("✅ 已推送到 Gist：%s\n" % raw)
            if not gid:
                sys.stderr.write("   把上面链接填进 App「设置→真实数据Gist」；或记好 GIST_REAL_ID=%s 以便后续更新。\n" % new_id)

    # 可选：git 提交推送
    try:
        import subprocess
        have_git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=BASE,
                                  capture_output=True).returncode == 0
    except Exception:
        have_git = False
    if have_git:
        _git_commit_push(["data.real.json", "prodimg"],
                         "chore: 更新电脑线材真实榜单 %s" % datetime.date.today().isoformat())
    else:
        sys.stderr.write("（当前目录非 git 仓库，跳过自动提交；请手动发布 data.real.json 与 prodimg/）\n")


if __name__ == "__main__":
    main()

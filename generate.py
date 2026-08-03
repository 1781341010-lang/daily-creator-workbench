#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日创作台 —— 数据生成与推送脚本
每天（北京时间 8 / 14 / 20 点）由 GitHub Actions 调度执行：
  1. 抓取 / AI 生成 7 大模块内容
  2. 组装成网页所需的 JSON
  3. 推送到一个「公开 GitHub Gist」，网页默认读取该 Gist

环境变量（都在仓库 Secrets 里配置）：
  GIST_TOKEN      有 gist 权限的 GitHub Token（必填，用于写 Gist）
  GIST_ID         已有 Gist 的 ID（留空则首次自动新建）
  NICHE_KEYWORDS  你的赛道关键词，逗号分隔（必填，产品/英语/热点都按它生成）
  PUBLIC_ACCOUNT  你的公众号来源名（用于热点模块的署名/口径，可选）
  OPENAI_API_KEY  LLM Key（不填则用规则兜底，仍能产出可用内容）
  OPENAI_BASE_URL OpenAI 兼容接口地址（默认 https://api.openai.com/v1）
  OPENAI_MODEL    模型名（默认 gpt-4o-mini）

说明（重要，实在话）：
  - 1688 / 阿里国际站有强反爬，Actions 无法直接稳定抓取真实商品。
    因此「产品二创」用 LLM 按你的赛道关键词生成「热门爆款 + 最新下单款式」，
    这正是你要的「用 AI 改写成贴合参考的内容」。
  - 新闻/基金/股票同理：有 LLM 时做整理归纳；未配 LLM 时用规则兜底，
    并在数据里标注 live=false，网页会正常显示但你知道是示意数据。
"""

import os, json, sys, datetime, random, urllib.request, urllib.error, urllib.parse

# ---------- 配置 ----------
GIST_TOKEN = os.environ.get("GIST_TOKEN", "")
GIST_ID = os.environ.get("GIST_ID", "")
NICHE = [k.strip() for k in (os.environ.get("NICHE_KEYWORDS", "") or "").split(",") if k.strip()]
PUBLIC_ACCOUNT = os.environ.get("PUBLIC_ACCOUNT", "")
LLM_KEY = os.environ.get("OPENAI_API_KEY", "")
LLM_BASE = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

GIST_FILENAME = "data.json"
GIST_DESC = "每日创作台 - 自动生成数据（公开）"

NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))  # 北京时间
TODAY = NOW.strftime("%Y-%m-%d")

random.seed(int(NOW.strftime("%Y%m%d")))  # 同一天结果稳定


# ---------- LLM 调用（OpenAI 兼容） ----------
def call_llm(system, user, expect_json=True):
    if not LLM_KEY:
        return None
    url = LLM_BASE + "/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.8,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + LLM_KEY,
                                           "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        sys.stderr.write("[LLM错误] %s\n" % e)
        return None


def extract_json(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e >= 0:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            return None
    return None


# ---------- 模块生成：英语练习 ----------
EN_POOL = [
    ("Serendipity", "/ˌserənˈdɪpəti/", ["高级词汇", "写作"], "意外发现珍奇事物的本领；机缘巧合。", "Finding this café was pure serendipity.", "发现这家咖啡馆纯属机缘巧合。"),
    ("Leverage", "/ˈliːvərɪdʒ/", ["商业", "高频"], "杠杆；充分利用资源或关系。", "We can leverage our network to grow faster.", "我们可以借助人脉网络更快成长。"),
    ("Resilience", "/rɪˈzɪliəns/", ["心理", "演讲"], "韧性；从挫折中恢复的能力。", "Resilience is a skill you can train.", "韧性是一项可以训练的能力。"),
    ("Cutting-edge", "/ˈkʌtɪŋ edʒ/", ["科技", "带货"], "尖端的；最前沿的。", "Our cutting-edge design stands out.", "我们前沿的设计脱颖而出。"),
    ("Pain point", "/peɪn pɔɪnt/", ["营销", "用户"], "痛点；用户真实的困扰。", "Solve the user's pain point first.", "先解决用户真正的痛点。"),
    ("Conversion", "/kənˈvɜːʃn/", ["电商", "数据"], "转化；访客变成客户的比例。", "A clear CTA boosts conversion.", "清晰的行动号召能提升转化。"),
    ("Niche", "/niːʃ/", ["定位", "选品"], "细分市场；小众赛道。", "Pick a niche you truly know.", "选一个你真正熟悉的细分领域。"),
    ("Hook", "/hʊk/", ["短视频", "开篇"], "钩子；开头留住人的一句话。", "The first 3 seconds are your hook.", "前 3 秒就是你的钩子。"),
    ("Engagement", "/ɪnˈɡeɪdʒmənt/", ["运营", "互动"], "互动量；评论/点赞/转发。", "Engagement beats follower count.", "互动量比粉丝数更重要。"),
    ("Organic", "/ɔːˈɡænɪk/", ["流量", "免费"], "自然流量；非付费来的。", "Organic reach is the real test.", "自然触达才是真正的考验。"),
    ("Scarcity", "/ˈskeəsəti/", ["营销", "转化"], "稀缺性；促单的心理杠杆。", "Scarcity drives faster decisions.", "稀缺感能促使更快下单。"),
    ("Persona", "/pəˈsəʊnə/", ["定位", "人设"], "人物画像；目标用户原型。", "Build a clear persona first.", "先建立一个清晰的人物画像。"),
    ("Call to action", "/kɔːl tə ˈækʃn/", ["带货", "文案"], "行动号召；引导用户下单/关注。", "End with a strong CTA.", "以一句有力的行动号召收尾。"),
    ("Churn", "/tʃɜːn/", ["运营", "留存"], "流失；用户停止使用的比例。", "Reduce churn with onboarding.", "用新手引导来降低流失。"),
    ("Viral", "/ˈvaɪrəl/", ["传播", "短视频"], "病毒式传播；自发扩散。", "Make it shareable to go viral.", "让它值得分享，才能病毒式传播。"),
    ("Margin", "/ˈmɑːdʒɪn/", ["电商", "利润"], "毛利；售价减成本。", "Watch your margin, not just revenue.", "盯紧毛利，而不只是营收。"),
    ("Funnel", "/ˈfʌnl/", ["增长", "转化"], "漏斗；从曝光到成交的路径。", "Optimize each step of the funnel.", "优化漏斗的每一步。"),
    ("Retention", "/rɪˈtenʃn/", ["运营", "留存"], "留存；用户持续回来的比例。", "Retention is cheaper than acquisition.", "留存比拉新更省钱。"),
    ("Testimonial", "/ˌtestɪˈməʊniəl/", ["信任", "带货"], "用户证言；真实好评。", "A video testimonial builds trust.", "一段视频证言能建立信任。"),
    ("Trend", "/trend/", ["热点", "选品"], "趋势；正在上升的方向。", "Ride the trend early, not late.", "趁早踩趋势，别等晚了。"),
]

def gen_english():
    if LLM_KEY and NICHE:
        sys_p = "你是英语内容编辑，输出严格 JSON：{\"english\":[{\"word\",\"phon\",\"tags\":[],\"desc\",\"eg\",\"trans\",\"topic\"}...]}，共10条。"
        usr = "赛道关键词：%s。生成10个该赛道创作者最该掌握的英文词/短语，含音标、中文说明、例句、例句的中文翻译(trans)、相关话题标签(topic)。" % "、".join(NICHE)
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("english"), list) and len(j["english"]) >= 5:
            return j["english"][:10]
    picks = random.sample(EN_POOL, 10)
    return [{"word": w, "phon": p, "tags": t, "desc": d, "eg": e, "trans": tr, "topic": (t[0] if t else "")} for (w, p, t, d, e, tr) in picks]


# ---------- 模块生成：今日热点（四大财经） ----------
NEWS_SOURCES = ["新华财经", "证券时报", "财联社", "21财经"]

def gen_news():
    if LLM_KEY:
        sys_p = "你是财经编辑，输出严格 JSON：{\"news\":[{\"src\",\"title\",\"sum\",\"url\",\"time\"}...]}，共4条，每条对应一个来源。"
        usr = ("今天是 %s。为以下四个来源各写一条当日热门财经快讯：%s。"
               "title 为标题，sum 为30字内摘要，url 用该媒体官网，time 用近似发布时间(HH:MM)。"
               % (TODAY, "、".join(NEWS_SOURCES)))
        if PUBLIC_ACCOUNT:
            usr += "可参考「%s」的口径。" % PUBLIC_ACCOUNT
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("news"), list) and len(j["news"]) >= 3:
            out = []
            for it in j["news"]:
                it.setdefault("src", "")
                it.setdefault("title", "")
                it.setdefault("sum", "")
                it.setdefault("url", "https://www.baidu.com/s?wd=" + urllib.parse.quote(it.get("title", "")))
                it.setdefault("time", "")
                out.append(it)
            return out
    # 规则兜底
    base = [
        ("央行公开市场操作维持流动性合理充裕，资金面平稳", "市场关注后续稳增长政策节奏。"),
        ("A股结构性行情延续，高股息与科技成长轮动", "成交温和放大，资金青睐确定性方向。"),
        ("北向资金小幅净流入，核心资产获逢低配置", "外资风险偏好边际改善。"),
        ("多家行业龙头披露经营数据，景气分化明显", "智能化与出海成共同主线。"),
    ]
    sites = {"新华财经": "https://www.news.cn/", "证券时报": "https://www.stcn.com/",
             "财联社": "https://www.cls.cn/", "21财经": "https://www.21jingji.com/"}
    res = []
    for i, src in enumerate(NEWS_SOURCES):
        t, s = base[i % len(base)]
        res.append({"src": src, "title": t, "sum": s, "url": sites.get(src, ""), "time": "%02d:%02d" % (8 + i * 1, 30)})
    return res


# ---------- 模块生成：产品二创（1688 / 阿里国际站） ----------
# 只聚焦一个类目：电脑线材（用户明确要求「电脑线材类目」真实数据）
# 每组输出：销量 TOP10（按前台累计销量）+ 最新上架 TOP10（按上架时间倒序）
# 说明：1688 / alibaba 都封锁机器人，规则版只生成「电脑线材」的示意样例（渐变占位，无随机图）；
#       真实主图 + 真实商品链接必须由本机登录态爬虫（scrape_real.py）抓取后写入 data.real.json 覆盖层。
TRACKS = [
  {"key":"cable","name":"电脑线材","kw":"cable",
   "tag_cn":"电脑线材","tag2_cn":"网络","tag_en":"Cable","tag2_en":"Network",
   "arch":[
    ("千兆网线 CAT6 成品线","Cat6 Ethernet Cable","做「网速拉满」布置，强调六类线稳定低延迟，适合游戏/直播。","Full-speed network setup, Cat6 stable low latency for gaming."),
    ("Type-C数据线 100W快充","Type C Cable 100W Fast Charge","打「一根线充电脑+手机」痛点，演示100W快充，强调编织耐拉。","One cable charges laptop+phone, 100W demo, braided."),
    ("编织Type-C线 240W","Braided Type C Cable 240W","打「大功率设备充电」场景，演示笔记本满速充，强调耐弯折。","High-power device charge, laptop full-speed, bend-proof."),
    ("HDMI高清线 2.1 8K","HDMI 2.1 Cable 8K","做「高清不模糊」对比，强调2.1版支持8K120Hz。","HD clear compare, 2.1 supports 8K120Hz."),
    ("Type-C转Lightning线","Type C to Lightning Cable","做「苹果用户」场景，演示快充+数据传输，强调MFi稳定。","Apple user scene, fast charge + data, stable."),
    ("雷电4数据线","Thunderbolt 4 Cable","打「高速传输」痛点，演示40Gbps传大文件，强调不掉速。","High-speed transfer pain, 40Gbps big files, no drop."),
    ("显示器连接线 DP线","DisplayPort Cable","做「高刷显示器」布置，演示2K/4K高刷，强调画面顺滑。","High-refresh monitor setup, 2K/4K high Hz, smooth."),
    ("磁吸充电线","Magnetic Charging Cable","打「盲插充电」痛点，演示一碰即吸，强调不分正反。","Blind-plug charge pain, magnetic snap, no orientation."),
    ("多合一数据线","Multi-in-1 Charging Cable","做「一根走天下」场景，演示多接头适配，强调出差必备。","One cable for all, multi-head adapter, travel must-have."),
    ("编织快充数据线","Braided Fast Charge Cable","打「耐拉不破」痛点，演示暴力弯折不坏，强调两年质保。","Tug-proof pain, violent bend no break, 2-year warranty."),
   ]},
]


# ---------- 真实产品图片：构建时按关键词拉取真实照片，落盘 prodimg/ 随站点同源托管 ----------
# 说明：1688/阿里国际站有强反爬，运行时无法直接抓真实商品图；且外部图床（如 Flickr）在国内常被墙。
# 因此在「生成/构建」阶段就把真实产品照片下载进仓库的 prodimg/ 目录，App 以相对路径同源加载，
# 用户手机访问的是站点自身域名，不走外部图床，国内稳定可加载、且无需登录。
# 图源用 LoremFlickr（Flickr 创用 CC 真实照片，按关键词返回），仅用于构建期下载。
import os as _os
_BASE_DIR = _os.path.dirname(_os.path.abspath(__file__))
IMG_DIR = _os.path.join(_BASE_DIR, "prodimg")
_IMG_CACHE = {}

# 类目标签 -> 英文搜索词（用于拉取对应真实产品照片）
_KW_MAP = {
    "USB HUB": "usb,hub",
    "Converter": "hdmi,adapter", "转换器": "hdmi,adapter",
    "Switch": "hdmi,switch", "切换器": "hdmi,switch", "KVM": "kvm,switch",
    "Capture Card": "video,capture,card", "视频采集卡": "video,capture,card",
    "Bluetooth": "bluetooth,adapter", "蓝牙适配器": "bluetooth,adapter",
    "Cable": "cable", "电脑线材": "cable",
    "Charge": "charger,cable", "充电": "charger,cable",
    "Office": "usb,adapter", "办公": "usb,adapter",
    "Digital": "usb,adapter", "数码": "usb,adapter",
    "Video": "hdmi,cable", "影音": "hdmi,cable",
    "Audio": "audio,adapter", "音频": "audio,adapter",
    "Network": "ethernet,cable", "网络": "ethernet,cable",
    "Computer": "usb,hub", "电脑外设": "usb,hub",
    "Live": "webcam,stream", "直播": "webcam,stream",
}
_DEFAULT_KW = "usb,adapter"

def _safe_name(name):
    out = []
    for ch in name:
        out.append(ch if (ch.isalnum() or ch in "-_") else "_")
    return "".join(out)[:40]

def _img_keywords(item):
    for t in item.get("tags", []) or []:
        if t in _KW_MAP:
            return _KW_MAP[t]
    for t in item.get("tags", []) or []:
        if t.isascii() and t.replace(" ", "").isalpha():
            return t.lower().replace(" ", ",")
    return _DEFAULT_KW

def _stable_hash(s):
    """稳定哈希（不依赖进程随机盐），保证同一天多次构建结果一致。"""
    import hashlib
    return int(hashlib.md5(str(s).encode("utf-8")).hexdigest(), 16)

def img_rel_path(item):
    """返回相对路径（如 prodimg/xxx.jpg），按「基础名」去新款后缀，确保销量/新品复用同一图。"""
    nm = item.get("name", "")
    base = nm.split("·2026新款")[0].split(" 2026 New")[0]
    return "prodimg/" + _safe_name(base) + ".jpg"

def download_one(item):
    """若图片不存在则下载（真实 Flickr CC 照片）；失败留空，App 回退渐变占位。"""
    path = _os.path.join(_BASE_DIR, img_rel_path(item))
    if _os.path.exists(path):
        return
    kw = _img_keywords(item)
    base = item.get("name", "").split("·2026新款")[0].split(" 2026 New")[0]
    try:
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        lock = _stable_hash(base) % 100000
        url = "https://loremflickr.com/480/360/%s?lock=%d" % (urllib.parse.quote(kw), lock)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        if len(data) > 1500 and data[:3] == b"\xff\xd8\xff":
            with open(path, "wb") as f:
                f.write(data)
        else:
            sys.stderr.write("[图片跳过] %s 非 JPEG\n" % item.get("name", ""))
    except Exception as e:
        sys.stderr.write("[图片下载失败] %s (%s): %s\n" % (item.get("name", ""), kw, e))

def prefetch_product_images(all_items, workers=8):
    """并行下载缺失的产品图，加速构建。"""
    seen, todo = set(), []
    for it in all_items:
        p = img_rel_path(it)
        if p not in seen:
            seen.add(p); todo.append(it)
    if not todo:
        return
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(download_one, todo))
    except Exception as e:
        sys.stderr.write("[图片预取异常] %s\n" % e)


def gen_track(track, plat_tag):
    """生成单个细分赛道的两组 TOP10：销量榜（按累计销量）+ 新品榜（按上架时间倒序）。"""
    arch = track["arch"]
    sales_items, new_items = [], []
    for (cn, en, cn_a, en_a) in arch:
        nm = cn if plat_tag == "1688" else en
        ang = cn_a if plat_tag == "1688" else en_a
        tg1 = track["tag_cn"] if plat_tag == "1688" else track["tag_en"]
        tg2 = track["tag2_cn"] if plat_tag == "1688" else track["tag2_en"]
        # 累计销量：按 日期+名称 稳定派生
        random.seed(_stable_hash((TODAY, nm, "s")) % 1000000)
        sales = random.randint(20000, 600000)
        # 上架天数：按 日期+名称 稳定派生（0=今天）
        random.seed(_stable_hash((TODAY, nm, "n")) % 1000000)
        days = random.randint(0, 25)
        # 规则样例：不挂任何图片（绝不拿随机图应付）。真实主图由本机爬虫写入覆盖层。
        s_it = {"name": nm, "plat": plat_tag, "sales": sales, "angle": ang, "tags": [tg1, tg2]}
        sales_items.append(s_it)
        # 新品榜用「新款」命名
        nm_new = (nm + "·2026新款") if plat_tag == "1688" else (nm + " 2026 New")
        n_it = {"name": nm_new, "plat": plat_tag, "listedDays": days,
                "listedAt": ("今天" if days == 0 else ("%d天前" % days)),
                "angle": ang, "tags": [tg1, tg2]}
        new_items.append(n_it)
    sales_items.sort(key=lambda x: x["sales"], reverse=True)
    new_items.sort(key=lambda x: x["listedDays"])
    return {"sales": sales_items[:10], "new": new_items[:10]}


def _rule_tracks(plat):
    tracks = []
    for t in TRACKS:
        g = gen_track(t, plat)
        tracks.append({"key": t["key"], "name": t["name"], "sales": g["sales"], "new": g["new"]})
    return {"tracks": tracks}

def gen_products():
    # 云端只产出规则样例（电脑线材），不挂图片、不声称实时。
    # 真实数据（真实主图 + 真实链接）由本机登录态爬虫 scrape_real.py 写入 data.real.json 覆盖层，
    # App 加载时优先叠加该覆盖层，从而显示「✅ 实时数据」。
    out = {}
    out["p1688"] = _rule_tracks("1688")
    out["pintl"] = _rule_tracks("阿里国际站")
    return out, False


# ---------- 模块生成：基金 / 股票（14:00 净流入榜） ----------
def _fallback_rank(names, with_price):
    res = []
    for nm, code in names:
        inflow = round(random.uniform(2.0, 13.0), 1)
        change = round(random.uniform(-1.5, 3.0), 2)
        item = {"name": nm, "code": code, "inflow": inflow, "change": change}
        if with_price:
            item["price"] = round(random.uniform(20, 1700), 2)
        res.append(item)
    res.sort(key=lambda x: x["inflow"], reverse=True)
    return res


FUND_NAMES = [("易方达蓝筹精选混合", "005827"), ("中欧医疗健康混合A", "003095"),
              ("招商中证白酒指数(LOF)", "161725"), ("华夏成长混合", "000001"),
              ("富国天惠成长混合(LOF)", "161005"), ("兴全合宜混合(LOF)", "163417"),
              ("景顺长城新兴成长混合", "260108"), ("睿远成长价值混合A", "007119"),
              ("易方达消费行业股票", "110022"), ("诺安成长混合", "320007")]
STOCK_NAMES = [("中芯国际", "688981"), ("贵州茅台", "600519"), ("宁德时代", "300750"),
               ("比亚迪", "002594"), ("北方华创", "002371"), ("招商银行", "600036"),
               ("隆基绿能", "601012"), ("立讯精密", "002475"), ("中国中免", "601888"), ("科大讯飞", "002230")]
ETF_NAMES = [("沪深300ETF", "510300"), ("科创50ETF", "588000"), ("中证500ETF", "510500"),
             ("创业板ETF", "159915"), ("券商ETF", "512000"), ("半导体ETF", "512760"),
             ("新能源车ETF", "515030"), ("黄金ETF", "518880"), ("纳指ETF", "513100"), ("军工ETF", "512660")]
SECTOR_NAMES = [("半导体", ""), ("新能源", ""), ("白酒", ""), ("医药", ""), ("军工", ""),
                ("证券", ""), ("光伏", ""), ("消费电子", ""), ("人工智能", ""), ("储能", "")]


def gen_funds():
    if LLM_KEY:
        sys_p = "你是基金数据分析师，输出严格 JSON：{\"funds\":[{\"name\",\"code\",\"inflow\":亿,\"change\":%}]...10条}，按净流入降序。"
        usr = "模拟今日14:00 净流入资金最大的10只具体基金（不要ETF，要具体基金名称如「易方达蓝筹精选混合」），inflow 为净流入亿元(1位小数)，change 为涨跌幅%。"
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("funds"), list) and len(j["funds"]) >= 5:
            return j["funds"]
    return _fallback_rank(FUND_NAMES, False)


def gen_stocks():
    if LLM_KEY:
        sys_p = "你是股票数据分析师，输出严格 JSON：{\"stocks\":[{\"name\",\"code\",\"price\":元,\"inflow\":亿,\"change\":%}]...10条}，按净流入降序。"
        usr = "模拟今日14:00 净流入资金最大的10只股票，price 为现价元，inflow 为净流入亿元(1位小数)，change 为涨跌幅%。"
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("stocks"), list) and len(j["stocks"]) >= 5:
            return j["stocks"]
    return _fallback_rank(STOCK_NAMES, True)


def gen_etfs():
    if LLM_KEY:
        sys_p = "你是基金数据分析师，输出严格 JSON：{\"etfs\":[{\"name\",\"code\",\"inflow\":亿,\"change\":%}]...10条}，按净流入降序。"
        usr = "模拟今日14:00 净流入资金最大的10只ETF（如沪深300ETF、科创50ETF），inflow 为净流入亿元(1位小数)，change 为涨跌幅%。"
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("etfs"), list) and len(j["etfs"]) >= 5:
            return j["etfs"]
    return _fallback_rank(ETF_NAMES, False)


def gen_sectors():
    if LLM_KEY:
        sys_p = "你是行业分析师，输出严格 JSON：{\"sectors\":[{\"name\",\"inflow\":亿,\"change\":%}]...10条}，按净流入降序。"
        usr = "模拟今日14:00 主力资金净流入最大的10个股票板块（如半导体、新能源、白酒、医药），inflow 为板块净流入亿元(1位小数)，change 为板块涨跌幅%。"
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("sectors"), list) and len(j["sectors"]) >= 5:
            return j["sectors"]
    return [{"name": nm, "code": "", "inflow": round(random.uniform(3.0, 20.0), 1),
            "change": round(random.uniform(-2.0, 4.0), 2)} for nm, _ in SECTOR_NAMES]


# ---------- 模块生成：巴菲特/芒格价值投资（每日 14:00 更新） ----------
BUFFETT_SEED = {
    "philosophy": "价格是你付出的，价值是你得到的。――沃伦·巴菲特",
    "marketTrend": "沪指围绕 3000 点震荡，成交量温和放大；价值股相对占优，市场情绪由恐慌转向中性。",
    "hft": "量化/高频资金今日净卖出约 12 亿，集中在题材炒作端；权重蓝筹获长线资金承接，高频扰动未改长期趋势。",
    "tomorrow": {"dir": "上涨", "conf": 62, "reason": "权重蓝筹估值合理 + 北向小幅回流，但量能不足，涨幅或有限。"},
    "strategy": "坚持能力圈与安全边际：只在看得懂、价格低于内在价值的生意上下注；用长期持有对冲短期噪音。",
    "picks": [
        {"name": "贵州茅台", "code": "600519", "action": "持有",
         "trend": "回踩年线获支撑，量价企稳", "buy": "1500-1550 分批", "sell": "1750 上方分批止盈",
         "logic": "强品牌 + 高自由现金流，符合护城河标准"},
        {"name": "招商银行", "code": "600036", "action": "买入",
         "trend": "低位横盘，股息率具吸引力", "buy": "35 以下", "sell": "42 上方",
         "logic": "零售银行龙头，资产质量稳健"},
        {"name": "长江电力", "code": "600900", "action": "持有",
         "trend": "慢牛上行，防御属性强", "buy": "25 附近", "sell": "30 上方",
         "logic": "稳定现金流 + 高分红，类债券资产"},
        {"name": "宁德时代", "code": "300750", "action": "观望",
         "trend": "震荡筑底，估值回归", "buy": "180-200 观察", "sell": "230 上方",
         "logic": "动力电池龙头，需等景气拐点确认"},
    ],
}

def gen_buffett():
    if LLM_KEY:
        sys_p = ("你是价值投资分析师，深研巴菲特与芒格理念。输出严格 JSON："
                 "{\"buffett\":{\"philosophy\":\"金句\",\"marketTrend\":\"行情趋势\",\"hft\":\"高频交易观测\","
                 "\"tomorrow\":{\"dir\":\"上涨或下跌\",\"conf\":0-100,\"reason\":\"理由\"},"
                 "\"strategy\":\"选股策略\",\"picks\":[{\"name\",\"code\",\"action\":\"买入/持有/观望\","
                 "\"trend\":\"走势\",\"buy\":\"买点\",\"sell\":\"卖点\",\"logic\":\"逻辑\"}...4条]}}。")
        usr = ("今天是 %s。参考巴菲特《聪明的投资者》《巴菲特致股东的信》与芒格《穷查理宝典》的理念，"
               "生成一份「每日 14:00」价值投资参考。要求：tomorrow.dir 为上涨或下跌二选一并给置信度；"
               "picks 给 4 只 A 股，含走势、买卖点位与能力圈/护城河逻辑；所有内容为中文，仅作学习参考，非投资建议。"
               % TODAY)
        j = extract_json(call_llm(sys_p, usr))
        b = j.get("buffett") if j else None
        if b and isinstance(b.get("picks"), list) and len(b["picks"]) >= 3:
            # 兜底字段，避免个别缺失导致前端显示异常
            b.setdefault("philosophy", BUFFETT_SEED["philosophy"])
            b.setdefault("marketTrend", BUFFETT_SEED["marketTrend"])
            b.setdefault("hft", BUFFETT_SEED["hft"])
            b.setdefault("strategy", BUFFETT_SEED["strategy"])
            t = b.setdefault("tomorrow", dict(BUFFETT_SEED["tomorrow"]))
            t.setdefault("dir", "上涨"); t.setdefault("conf", 60); t.setdefault("reason", "")
            clean = []
            for it in b["picks"][:4]:
                clean.append({"name": it.get("name", ""), "code": it.get("code", ""),
                              "action": it.get("action", "持有"), "trend": it.get("trend", ""),
                              "buy": it.get("buy", "—"), "sell": it.get("sell", "—"),
                              "logic": it.get("logic", "")})
            b["picks"] = clean
            return b
    return dict(BUFFETT_SEED)


# ---------- 组装 + 推送 ----------
def build_payload():
    prods, p1688_real = gen_products()
    return {
        "updatedAt": int(NOW.timestamp() * 1000),
        "live": p1688_real,   # 仅当本机用 Cookie 真实抓到 1688 榜单才为 True；云端规则版恒为 False
        "english": gen_english(),
        "news": gen_news(),
        "p1688": prods["p1688"],
        "pintl": prods["pintl"],
        "funds": gen_funds(),
        "stocks": gen_stocks(),
        "etfs": gen_etfs(),
        "sectors": gen_sectors(),
        "buffett": gen_buffett(),
    }


def push_gist(payload):
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    if not GIST_TOKEN:
        # 无 token：落本地，便于调试
        with open(GIST_FILENAME, "w", encoding="utf-8") as f:
            f.write(content)
        sys.stderr.write("[提示] 未配置 GIST_TOKEN，已写入本地 %s\n" % GIST_FILENAME)
        return None
    headers = {"Authorization": "Bearer " + GIST_TOKEN, "Content-Type": "application/json",
               "Accept": "application/vnd.github+json", "User-Agent": "daily-creator"}
    if GIST_ID:
        url = "https://api.github.com/gists/" + GIST_ID
        body = {"files": {GIST_FILENAME: {"content": content}}, "description": GIST_DESC}
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="PATCH")
    else:
        url = "https://api.github.com/gists"
        body = {"public": True, "description": GIST_DESC,
                "files": {GIST_FILENAME: {"content": content}}}
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        gid = data.get("id")
        raw = "https://gist.githubusercontent.com/%s/%s/raw/%s" % (data["owner"]["login"], gid, GIST_FILENAME)
        sys.stderr.write("[OK] Gist 已更新：%s\n" % raw)
        # 把 Gist ID 写回，方便下次更新（仅本地提示）
        if not GIST_ID:
            sys.stderr.write("[GIST_ID] %s\n" % gid)
        return raw
    except urllib.error.HTTPError as e:
        sys.stderr.write("[Gist错误] %s %s\n" % (e.code, e.read().decode("utf-8", "ignore")[:300]))
        return None
    except Exception as e:
        sys.stderr.write("[Gist错误] %s\n" % e)
        return None


if __name__ == "__main__":
    payload = build_payload()
    # 注意：规则样例不挂图片（避免随机图）；真实主图由本机 scrape_real.py 抓取后写入 prodimg/ 与覆盖层。
    raw = push_gist(payload)
    # 同时落一份本地，方便核对
    with open(GIST_FILENAME, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps({"updatedAt": payload["updatedAt"], "live": payload["live"],
                      "counts": {"english": len(payload["english"]), "news": len(payload["news"]),
                                 "p1688_tracks": len(payload["p1688"]["tracks"]),
                                 "pintl_tracks": len(payload["pintl"]["tracks"]),
                                 "funds": len(payload["funds"]), "stocks": len(payload["stocks"]),
                                 "etfs": len(payload["etfs"]), "sectors": len(payload["sectors"]),
                                 "buffett": len(payload["buffett"]["picks"])},
                      "gist_raw": raw}, ensure_ascii=False))

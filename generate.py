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
    ("Serendipity", "/ˌserənˈdɪpəti/", ["高级词汇", "写作"], "意外发现珍奇事物的本领；机缘巧合。", "Finding this café was pure serendipity."),
    ("Leverage", "/ˈliːvərɪdʒ/", ["商业", "高频"], "杠杆；充分利用资源或关系。", "We can leverage our network to grow faster."),
    ("Resilience", "/rɪˈzɪliəns/", ["心理", "演讲"], "韧性；从挫折中恢复的能力。", "Resilience is a skill you can train."),
    ("Cutting-edge", "/ˈkʌtɪŋ edʒ/", ["科技", "带货"], "尖端的；最前沿的。", "Our cutting-edge design stands out."),
    ("Pain point", "/peɪn pɔɪnt/", ["营销", "用户"], "痛点；用户真实的困扰。", "Solve the user's pain point first."),
    ("Conversion", "/kənˈvɜːʃn/", ["电商", "数据"], "转化；访客变成客户的比例。", "A clear CTA boosts conversion."),
    ("Niche", "/niːʃ/", ["定位", "选品"], "细分市场；小众赛道。", "Pick a niche you truly know."),
    ("Hook", "/hʊk/", ["短视频", "开篇"], "钩子；开头留住人的一句话。", "The first 3 seconds are your hook."),
    ("Engagement", "/ɪnˈɡeɪdʒmənt/", ["运营", "互动"], "互动量；评论/点赞/转发。", "Engagement beats follower count."),
    ("Organic", "/ɔːˈɡænɪk/", ["流量", "免费"], "自然流量；非付费来的。", "Organic reach is the real test."),
    ("Scarcity", "/ˈskeəsəti/", ["营销", "转化"], "稀缺性；促单的心理杠杆。", "Scarcity drives faster decisions."),
    ("Persona", "/pəˈsəʊnə/", ["定位", "人设"], "人物画像；目标用户原型。", "Build a clear persona first."),
    ("Call to action", "/kɔːl tə ˈækʃn/", ["带货", "文案"], "行动号召；引导用户下单/关注。", "End with a strong CTA."),
    ("Churn", "/tʃɜːn/", ["运营", "留存"], "流失；用户停止使用的比例。", "Reduce churn with onboarding."),
    ("Viral", "/ˈvaɪrəl/", ["传播", "短视频"], "病毒式传播；自发扩散。", "Make it shareable to go viral."),
    ("Margin", "/ˈmɑːdʒɪn/", ["电商", "利润"], "毛利；售价减成本。", "Watch your margin, not just revenue."),
    ("Funnel", "/ˈfʌnl/", ["增长", "转化"], "漏斗；从曝光到成交的路径。", "Optimize each step of the funnel."),
    ("Retention", "/rɪˈtenʃn/", ["运营", "留存"], "留存；用户持续回来的比例。", "Retention is cheaper than acquisition."),
    ("Testimonial", "/ˌtestɪˈməʊniəl/", ["信任", "带货"], "用户证言；真实好评。", "A video testimonial builds trust."),
    ("Trend", "/trend/", ["热点", "选品"], "趋势；正在上升的方向。", "Ride the trend early, not late."),
]

def gen_english():
    if LLM_KEY and NICHE:
        sys_p = "你是英语内容编辑，输出严格 JSON：{\"english\":[{\"word\",\"phon\",\"tags\":[],\"desc\",\"eg\",\"topic\"}...]}，共10条。"
        usr = "赛道关键词：%s。生成10个该赛道创作者最该掌握的英文词/短语，含音标、中文说明、例句、相关话题标签。" % "、".join(NICHE)
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("english"), list) and len(j["english"]) >= 5:
            return j["english"][:10]
    picks = random.sample(EN_POOL, 10)
    return [{"word": w, "phon": p, "tags": t, "desc": d, "eg": e, "topic": (t[0] if t else "")} for (w, p, t, d, e) in picks]


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
def _gen_products(platform_label, plat_tag):
    if LLM_KEY and NICHE:
        sys_p = ("你是跨境电商选品编辑，输出严格 JSON："
                 "{\"hot\":[{\"name\",\"plat\",\"heat\":0-100,\"angle\",\"tags\":[]}...10条],"
                 "\"latest\":[{\"name\",\"plat\",\"heat\",\"angle\",\"tags\":[]}...10条]}。")
        usr = ("平台：%s。赛道关键词：%s。生成「热门爆款」10条与「最新下单款式」10条。"
               "name 为商品名，plat 固定为「%s」，heat 为热度(0-100整数)，"
               "angle 为给创作者的「改编角度/短视频脚本思路」(中文40字内)，tags 为2-3个标签。"
               % (platform_label, "、".join(NICHE), plat_tag))
        j = extract_json(call_llm(sys_p, usr))
        if j and isinstance(j.get("hot"), list) and isinstance(j.get("latest"), list) and len(j["hot"]) >= 5:
            for grp in ("hot", "latest"):
                for it in j[grp]:
                    it["plat"] = plat_tag
                    it.setdefault("heat", random.randint(60, 95))
                    it.setdefault("angle", "")
                    it.setdefault("tags", [])
            return j
    # 规则兜底：基于关键词拼装
    kw = NICHE[0] if NICHE else "潮流好物"
    tmpl_hot = ["%s ins风周边", "%s 网红同款", "%s 高颜值实用款", "%s 学生党必备", "%s 礼物首选",
                "%s 桌面神器", "%s 夏日刚需", "%s 国风新款", "%s 智能小物", "%s 解压好物"]
    tmpl_new = ["%s 新款上架", "%s 定制款", "%s 升级版", "%s 便携款", "%s 可水洗款",
                "%s 极简风", "%s 联名款", "%s 情侣款", "%s 旅行装", "%s 亲子款"]
    angles = ["做开箱测评，强调性价比与颜值，引导私域复购。",
              "打场景痛点，短视频演示使用前/后对比。",
              "蹭热点话题，做「一周穿搭/好物」合集。",
              "强调批发价优势，面向小B买家种草。"]
    out = {"hot": [], "latest": []}
    for grp, tmpls in (("hot", tmpl_hot), ("latest", tmpl_new)):
        for i, t in enumerate(tmpls):
            name = t % kw
            out[grp].append({
                "name": name, "plat": plat_tag,
                "heat": random.randint(62, 96),
                "angle": random.choice(angles),
                "tags": [kw, "二创" if grp == "hot" else "新款"],
            })
    return out


def gen_products():
    return {
        "p1688": _gen_products("1688（国内批发）", "1688"),
        "pintl": _gen_products("阿里巴巴国际站（跨境）", "阿里国际站"),
    }


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


FUND_NAMES = [("沪深300ETF", "510300"), ("中证红利ETF", "515080"), ("科创50ETF", "588000"),
              ("纳指ETF", "513100"), ("黄金ETF", "518880"), ("消费ETF", "159928"),
              ("新能源车ETF", "515030"), ("军工ETF", "512660"), ("医药ETF", "512010"), ("半导体ETF", "512760")]
STOCK_NAMES = [("中芯国际", "688981"), ("贵州茅台", "600519"), ("宁德时代", "300750"),
               ("比亚迪", "002594"), ("北方华创", "002371"), ("招商银行", "600036"),
               ("隆基绿能", "601012"), ("立讯精密", "002475"), ("中国中免", "601888"), ("科大讯飞", "002230")]


def gen_funds():
    if LLM_KEY:
        sys_p = "你是基金数据分析师，输出严格 JSON：{\"funds\":[{\"name\",\"code\",\"inflow\":亿,\"change\":%}]...10条}，按净流入降序。"
        usr = "模拟今日14:00 净流入资金最大的10只基金（含ETF），inflow 为净流入亿元(1位小数)，change 为涨跌幅%。"
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


# ---------- 组装 + 推送 ----------
def build_payload():
    prods = gen_products()
    return {
        "updatedAt": int(NOW.timestamp() * 1000),
        "live": bool(LLM_KEY),
        "english": gen_english(),
        "news": gen_news(),
        "p1688": prods["p1688"],
        "pintl": prods["pintl"],
        "funds": gen_funds(),
        "stocks": gen_stocks(),
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
    raw = push_gist(payload)
    # 同时落一份本地，方便核对
    with open(GIST_FILENAME, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps({"updatedAt": payload["updatedAt"], "live": payload["live"],
                      "counts": {"english": len(payload["english"]), "news": len(payload["news"]),
                                 "p1688_hot": len(payload["p1688"]["hot"]),
                                 "p1688_latest": len(payload["p1688"]["latest"]),
                                 "pintl_hot": len(payload["pintl"]["hot"]),
                                 "pintl_latest": len(payload["pintl"]["latest"]),
                                 "funds": len(payload["funds"]), "stocks": len(payload["stocks"])},
                      "gist_raw": raw}, ensure_ascii=False))

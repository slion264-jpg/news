#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""갈피 정적 사이트 생성기.

  python3 build.py            # data.json → public/*.html
의존성 없음. 결과물은 그대로 Firebase Hosting에 올릴 수 있는 정적 파일이다.
"""
import html
import itertools
import json
import math
import os
import re
import shutil
from collections import Counter
from urllib.parse import urlparse

import content as C

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "public")
DATA_PATH = os.path.join(ROOT, "data.json")

CATS = ["정치", "경제", "사회", "국제", "문화", "스포츠"]
CC = {"정치": "#3B5BDB", "경제": "#0B7A5E", "사회": "#C2410C",
      "국제": "#6D3FC4", "문화": "#C2255C", "스포츠": "#0C7C99"}
STK = {"찬성": "pro", "반대": "con", "제기": "neu"}
WD = ["일", "월", "화", "수", "목", "금", "토"]

D = json.load(open(DATA_PATH, encoding="utf-8"))
META, LABEL, TREND = D["meta"], D["label"], D["trend"]
ART = {a["id"]: a for a in D["articles"]}
TOPICS = D["topics"]
TMAP = {t["id"]: t for t in TOPICS}
DATES = META["dates"]

e = lambda s: html.escape(str(s), quote=True)
lb = lambda w: LABEL.get(w, w)
md = lambda d: d[5:].replace("-", "/")


def wd(d):
    y, m, day = (int(x) for x in d.split("-"))
    # Zeller 없이: 1970-01-01(목)부터의 일수
    a = (14 - m) // 12
    yy = y - a
    mm = m + 12 * a - 3
    jdn = day + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    return WD[(jdn + 1) % 7]


def host_of(url):
    return urlparse(url).netloc.replace("www.", "")


def is_nofetch(url):
    h = host_of(url)
    return any(h == d or h.endswith("." + d) for d in C.NO_FETCH_DOMAINS)


# ── 분석 ────────────────────────────────────────────────
# 표본이 작을 때 φ 값만으로는 근거의 두께를 구분할 수 없다. 기사 2건씩만 등장하는 두 단어가
# 우연히 한 기사에 같이 나오면 φ ≈ 0.50 이 나오는데, 이는 30건씩 등장하며 15건을 공유하는
# 진짜 강한 관계(φ ≈ 0.43)보다 높다. 그래서 φ 크기와 별개로 두 가지 관문을 둔다.
MIN_CO = 2          # 최소 공동등장 기사 수
Q_FDR = 0.05        # 벤저미니-호흐베르크 거짓발견율 상한


def fisher_right(n11, n10, n01, n00):
    """2×2 분할표의 피셔 정확검정 단측(우측) p값. 근사 없이 정확히 계산한다."""
    r1, r2, c1 = n11 + n10, n01 + n00, n11 + n01
    tot = math.comb(r1 + r2, c1)
    s = sum(math.comb(r1, k) * math.comb(r2, c1 - k)
            for k in range(n11, min(r1, c1) + 1))
    return s / tot


def analyze(i0=0, i1=None):
    i1 = len(DATES) - 1 if i1 is None else i1
    s, en = DATES[i0], DATES[i1]
    arts = [a for a in D["articles"] if s <= a["date"] <= en]
    n = len(arts)
    min_df = 2 if (i1 - i0 + 1) >= 3 else 1
    sets = {}
    for a in arts:
        for w in set(a["terms"]):
            sets.setdefault(w, set()).add(a["id"])
    terms = sorted([w for w in sets if len(sets[w]) >= min_df],
                   key=lambda w: (-len(sets[w]), w))
    cand = []
    for x, y in itertools.combinations(terms, 2):
        A, B = sets[x], sets[y]
        n11 = len(A & B)
        if n11 < MIN_CO:          # 우연한 1건 동시등장을 강한 상관으로 읽는 것을 막는다
            continue
        n10, n01 = len(A) - n11, len(B) - n11
        n00 = n - n11 - n10 - n01
        den = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        if den <= 0:
            continue
        phi = (n11 * n00 - n10 * n01) / den
        if phi <= 0:
            continue
        cand.append((fisher_right(n11, n10, n01, n00), x, y, round(phi, 4), n11))
    # 검정한 가설 수 = 가능한 모든 쌍. 쌍이 많을수록 우연히 유의해 보이는 쌍도 늘어나므로
    # 벤저미니-호흐베르크 절차로 거짓발견율(FDR)을 q 이하로 묶는다.
    m = max(len(terms) * (len(terms) - 1) // 2, 1)
    cand.sort()
    keep = 0
    for i, c in enumerate(cand, 1):
        if c[0] <= Q_FDR * i / m:
            keep = i
    links = [(x, y, phi, n11, p) for p, x, y, phi, n11 in cand[:keep]]
    cat = {}
    for w in terms:
        c = Counter(ART[i]["cat"] for i in sets[w])
        # 동률일 때 CATS 순서로 끊는다. most_common 만 쓰면 빌드마다 결과가 달라진다.
        cat[w] = min(c.items(), key=lambda kv: (-kv[1], CATS.index(kv[0])))[0]
    # 부상 · 소멸
    rising = falling = []
    if i1 - i0 + 1 >= 2:
        mid = i0 + (i1 - i0 + 1) // 2
        inA = lambda a: DATES[i0] <= a["date"] < DATES[mid]
        nA = sum(1 for a in arts if inA(a)) or 1
        nB = (n - nA) or 1
        dfa, dfb = Counter(), Counter()
        for a in arts:
            for w in set(a["terms"]):
                (dfa if inA(a) else dfb)[w] += 1
        rows = []
        for w in set(dfa) | set(dfb):
            a_, b_ = dfa[w], dfb[w]
            d = b_ / nB - a_ / nA
            if a_ + b_ >= 2 and abs(d) >= 0.02:
                rows.append((w, a_, b_, d))
        rising = sorted([r for r in rows if r[3] > 0], key=lambda r: -r[3])[:8]
        falling = sorted([r for r in rows if r[3] < 0], key=lambda r: r[3])[:8]
    return {"terms": terms, "df": {w: len(sets[w]) for w in terms}, "cat": cat,
            "links": links, "rising": rising, "falling": falling, "count": n}


A = analyze()


def tstat(t):
    arts = t["articles"]
    ops = t["opinions"]
    pro = sum(1 for o in ops if o["stance"] == "찬성")
    con = sum(1 for o in ops if o["stance"] == "반대")
    neu = sum(1 for o in ops if o["stance"] == "제기")
    ds = sorted(ART[i]["date"] for i in arts if i in ART)
    return {"t": t, "n": len(arts), "ops": len(ops), "pro": pro, "con": con, "neu": neu,
            "clash": 2 * min(pro, con) + (pro + con) * 0.25,
            "first": ds[0] if ds else "", "last": ds[-1] if ds else ""}


STATS = [tstat(t) for t in TOPICS]

# ── 셸 ────────────────────────────────────────────────
NAV = [("index.html", "홈"), ("explore.html", "네트워크"), ("topics.html", "토픽"),
       ("archive.html", "기사"), ("game.html", "오늘의 낱말"),
       ("method.html", "분석 방법"), ("policy.html", "이용 정책")]

MARK = ('<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">'
        '<line x1="5" y1="6" x2="15" y2="4" stroke="#7C8899" stroke-width="1"/>'
        '<line x1="5" y1="6" x2="9" y2="16" stroke="#7C8899" stroke-width="1"/>'
        '<line x1="15" y1="4" x2="17" y2="14" stroke="#7C8899" stroke-width="1"/>'
        '<line x1="9" y1="16" x2="17" y2="14" stroke="#7C8899" stroke-width="1"/>'
        '<circle cx="5" cy="6" r="2.4" fill="#3B5BDB"/><circle cx="15" cy="4" r="1.7" fill="#C2410C"/>'
        '<circle cx="9" cy="16" r="3.1" fill="#12161C"/><circle cx="17" cy="14" r="1.9" fill="#0B7A5E"/></svg>')


def nav(cur, depth=0):
    up = "../" * depth
    li = "".join(
        f'<a class="nav-link" data-on="{1 if h == cur else 0}" href="{up}{h}">{n}</a>'
        for h, n in NAV)
    return (f'<nav class="nav"><a class="nav-mark" href="{up}index.html">{MARK}'
            f'<b>갈피</b></a><div class="nav-links">{li}</div>'
            f'<span class="nav-span num">{md(META["range"][0])} – {md(META["range"][1])}'
            f' · 기사 {META["articles"]}건</span></nav>')


def foot(depth=0):
    up = "../" * depth
    return (f'<div class="wrap"><div class="foot"><div><strong>갈피</strong> — '
            f'국내 주요 언론 보도 {META["articles"]}건을 키워드 태깅해 단어 간 파이(φ) 상관을 '
            f'계산하고, 토픽과 의견, 원문 기사로 이어지는 4계층 구조로 정리한 비영리 사이트입니다.'
            f'</div><div style="margin-top:10px">모든 인용과 수치는 원문 기사로 연결됩니다. '
            f'토픽·의견 분류는 기사 원문을 근거로 사람이 정리한 것으로 자동 추출 결과가 아닙니다. '
            f'수집 범위와 저작권 입장은 <a href="{up}policy.html">이용 정책</a>, 계산 방법은 '
            f'<a href="{up}method.html">분석 방법</a>을 참고하세요.</div></div></div>')


def page(fname, title, desc, body, depth=0, extra_head="", extra_js="", bare=False):
    up = "../" * depth
    doc = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image">
<meta property="og:image" content="{up}assets/cover.png">
<link rel="icon" href="{up}assets/favicon.svg">
<link rel="stylesheet" href="{up}assets/site.css">{extra_head}</head>
<body>{nav(fname if depth == 0 else NAV_PARENT.get(fname, fname), depth)}
{body}
{'' if bare else foot(depth)}
{extra_js}</body></html>"""
    path = os.path.join(OUT, fname)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(doc)


NAV_PARENT = {}


# ── 조각 ────────────────────────────────────────────────
# ── 대립 표시 ──────────────────────────────────────────
# 같은 개념은 어디서든 같은 모양으로 그린다. 배지 문구만 읽어도 뜻이 통해야 하고
# 산식을 알 필요가 없어야 한다.
SB = {"팽팽": "even", "기울어짐": "tilt", "원사이드": "one",
      "문제제기만": "only", "의견 없음": "none"}


def stance_of(s):
    p, c, n = s["pro"], s["con"], s["neu"]
    if p and c:
        return "팽팽" if min(p, c) / max(p, c) >= 0.4 else "기울어짐"
    if p or c:
        return "원사이드"
    return "문제제기만" if n else "의견 없음"


def stancebar(s, size=""):
    p, c, n = s["pro"], s["con"], s["neu"]
    tot = p + c + n
    st = stance_of(s)
    if tot:
        seg = (f'<i class="sb-con" style="width:{c / tot * 100:.1f}%"></i>'
               f'<i class="sb-neu" style="width:{n / tot * 100:.1f}%"></i>'
               f'<i class="sb-pro" style="width:{p / tot * 100:.1f}%"></i>')
    else:
        seg = '<i class="sb-non" style="width:100%"></i>'
    leg = []
    if c: leg.append(f'<span class="c-con">반대 {c}</span>')
    if n: leg.append(f'<span class="c-neu">제기 {n}</span>')
    if p: leg.append(f'<span class="c-pro">찬성 {p}</span>')
    if st == "원사이드": leg.append("반론 없음")
    return (f'<div class="sb {size}"><span class="sb-badge {SB[st]}">{st}</span>'
            f'<span class="sb-bar">{seg}</span>'
            f'<span class="sb-legend">{" ".join(leg) or "수집된 발언 없음"}</span></div>')


def article_row(aid):
    a = ART.get(aid)
    if not a:
        return ""
    tag = '<span class="nofetch" title="robots.txt에 따라 본문을 조회하지 않는 매체">링크만</span>' if is_nofetch(a["url"]) else ""
    return (f'<a class="row-article" href="{e(a["url"])}" target="_blank" rel="noopener noreferrer">'
            f'<time class="num">{md(a["date"])}</time><span class="outlet">{e(a["outlet"])}</span>'
            f'{tag}<span class="t">{e(a["title"])}</span><span class="x">↗</span></a>')


def strip(vals, color=None):
    mx = max(1, max(vals))
    bars = "".join(
        f'<div class="strip-col"><u class="num">{v}</u>'
        f'<span style="height:{max(4, v / mx * 66):.0f}px'
        f'{";background:" + color if color and v else ";background:var(--rule)" if color else ""}"></span></div>'
        for v in vals)
    xs = "".join(f'<u class="num">{md(d)}</u>' for d in DATES)
    return (f'<div class="strip"><div class="strip-h">일별 기사 수</div>'
            f'<div class="strip-bars">{bars}</div><div class="strip-x">{xs}</div></div>')


def table(rows):
    tr = "".join(f'<tr><td style="font-weight:650">{e(o)}</td>'
                 f'<td class="host">{e(h)}</td><td>{e(n)}</td></tr>' for o, h, n in rows)
    return ('<table class="tbl"><thead><tr><th style="width:128px">언론사</th>'
            '<th class="host">도메인</th><th>robots.txt 확인 결과</th></tr></thead>'
            f'<tbody>{tr}</tbody></table>')


# ── 홈 ────────────────────────────────────────────────
def build_index():
    top5 = sorted(STATS, key=lambda s: -s["n"])[:5]
    clash = sorted([s for s in STATS if s["pro"] and s["con"]], key=lambda s: -s["clash"])[:5]
    # 반론 없이 한쪽 주장만 실린 토픽. 보도량이 많은 것부터 보여 준다.
    oneside = sorted([s for s in STATS if stance_of(s) == "원사이드"], key=lambda s: -s["n"])[:4]
    rank = "".join(
        f'<a class="rank-open" href="topics/{s["t"]["id"]}.html">'
        f'<span class="rank-i num">{i + 1:02d}</span><span>'
        f'<span class="rank-title">{e(s["t"]["label"])}</span>'
        f'<span class="rank-sum">{e(s["t"]["summary"])}</span>'
        f'<span class="rank-meta"><span style="color:{CC[s["t"]["cat"]]}">{s["t"]["cat"]}</span>'
        f'<span class="num">보도 {md(s["first"])} ~ {md(s["last"])}</span>'
        f'<span class="num">의견 {s["ops"]}건</span></span>'
        f'<span style="display:block;margin-top:8px;max-width:230px">{stancebar(s, "mini")}</span></span>'
        f'<span class="rank-side"><b class="num">{s["n"]}</b>기사</span></a>'
        for i, s in enumerate(top5))
    clrow = lambda lst: "".join(
        f'<a class="cl-row" href="topics/{s["t"]["id"]}.html"><span>'
        f'<span class="cl-name">{e(s["t"]["label"])}</span>'
        f'<span class="cl-sub">{s["t"]["cat"]} · 기사 {s["n"]}건 · 의견 {s["ops"]}건</span></span>'
        f'{stancebar(s, "lg")}</a>' for s in lst)
    cl, one = clrow(clash), clrow(oneside)
    n_one = sum(1 for s in STATS if stance_of(s) == "원사이드")
    duo = lambda rows, k: "".join(
        f'<div class="duo-row"><span>{e(lb(w))}</span><em class="num">{a_} → {b_}건 · '
        f'{"+" if d > 0 else ""}{d * 100:.0f}%p</em></div>' for w, a_, b_, d in rows[:7])
    chips = "".join(
        f'<a class="chip" href="explore.html?w={e(w)}" style="color:{CC[A["cat"][w]]}">'
        f'<span style="color:var(--ink-2)">{e(lb(w))}</span><b class="num">{A["df"][w]}</b></a>'
        for w in A["terms"][:12])

    body = f"""<div class="wrap">
<header class="hero"><div>
<div class="eyebrow">뉴스 상관 분석 · 대한민국 · 누적 {len(DATES)}일</div>
<h1>뉴스의 갈피를<br>단어와 대립으로 잡습니다</h1>
<p>단어 상관으로 이슈를 묶고, 각 이슈에 실린 찬반을 나란히 놓습니다.
<a href="method.html" style="color:var(--accent)">분석 방법 →</a></p>
<div class="kpis">
<div class="kpi"><b class="num">{META["articles"]}</b><span>수집 기사</span></div>
<div class="kpi"><b class="num">{len(A["terms"])}</b><span>분석 키워드</span></div>
<div class="kpi"><b class="num">{META["topics"]}</b><span>토픽</span></div>
<div class="kpi"><b class="num">{META["opinions"]}</b><span>제기된 의견</span></div></div>
<a class="cta" href="explore.html">네트워크 열기 <i>→</i></a>
</div>{strip(META["daily"])}</header>

<section><div class="sec-head"><h2>오늘의 키워드</h2></div>
<p class="sec-note">누르면 네트워크에서 열립니다</p>
<div class="chips">{chips}</div></section>

<section><div class="sec-head"><h2>가장 팽팽한 이슈</h2></div>
<p class="sec-note">찬성과 반대가 모두 두터운 이슈</p><div>{cl}</div></section>

<section><div class="sec-head"><h2>원사이드</h2><span class="eyebrow">{n_one}건</span></div>
<p class="sec-note">반론 없이 한쪽 주장만 실린 이슈</p><div>{one}</div></section>

<section><div class="sec-head"><h2>보도량이 가장 많은 이슈</h2><span class="eyebrow">TOP 5</span></div>
<p class="sec-note">기사 수 기준</p>
<div class="rank-list">{rank}</div></section>

<section><div class="sec-head"><h2>부상 · 소멸 키워드</h2></div>
<p class="sec-note">기간 전반 대 후반의 등장률 차이</p>
<div class="duo"><div class="duo-col"><div class="duo-h up">▲ 부상 키워드</div>{duo(A["rising"], 1)}</div>
<div class="duo-col"><div class="duo-h down">▼ 소멸 키워드</div>{duo(A["falling"], 0)}</div></div></section>

<a class="game-cta" href="game.html"><div>
<b>오늘의 낱말</b>
<span>어제 뉴스에 가장 많이 등장한 단어를 자모 여섯 번으로 맞혀 보세요</span>
</div><i>→</i></a>

<div class="guide">
<a href="method.html"><b>이 숫자들은 어떻게 나왔나</b><span>수집·태깅부터 상관 계산과 한계까지</span></a>
<a href="policy.html"><b>무엇을 싣고 무엇을 싣지 않나</b><span>수집 범위와 저작권 입장</span></a>
<a href="explore.html"><b>직접 기간을 바꿔 보려면</b><span>네트워크 탐색기에서 그 자리에서 재계산</span></a>
</div>
</div>"""
    page("index.html", f"갈피 — {META['range'][0]}~{META['range'][1]} 대한민국 뉴스 상관 분석",
         f"국내 보도 {META['articles']}건을 키워드로 태깅해 단어 상관 네트워크를 그리고, "
         "기간을 바꾸면 그 자리에서 다시 계산합니다. 단어에서 토픽, 찬반 의견, 원문 기사까지.", body)


# ── 토픽 목록 ────────────────────────────────────────────
def build_topics():
    cards = "".join(
        f'<a class="tcard" data-cat="{s["t"]["cat"]}" data-n="{s["n"]}" data-o="{s["ops"]}" '
        f'data-c="{s["clash"]:.2f}" data-last="{s["last"]}" '
        f'data-q="{e(s["t"]["label"] + " " + s["t"]["summary"])}" '
        f'href="topics/{s["t"]["id"]}.html" style="border-top-color:{CC[s["t"]["cat"]]}">'
        f'<div class="eyebrow" style="color:{CC[s["t"]["cat"]]}">{s["t"]["cat"]}</div>'
        f'<h3>{e(s["t"]["label"])}</h3><p>{e(s["t"]["summary"])}</p>'
        f'<div class="tcard-meta"><span class="num">기사 {s["n"]}</span>'
        f'<span class="num">의견 {s["ops"]}</span>'
        f'<span class="num">{md(s["first"])}~{md(s["last"])}</span></div>'
        f'<div style="margin-top:9px">{stancebar(s)}</div></a>'
        for s in sorted(STATS, key=lambda s: -s["n"]))
    cattabs = "".join(
        f'<button class="tab" data-f="{c}">{c} {sum(1 for s in STATS if s["t"]["cat"] == c)}</button>'
        for c in CATS if any(s["t"]["cat"] == c for s in STATS))
    body = f"""<div class="wrap">
<div style="padding:44px 0 8px"><h1 class="doc-h1" style="margin:0">토픽 {len(TOPICS)}건</h1>
<p class="doc-lead" style="max-width:62ch">수록 기간 동안 국내 보도에서 반복해 다뤄진 사안을 토픽으로 묶고,
각 토픽에 제기된 찬성·반대·문제제기 의견을 원문 기사와 함께 붙였습니다.</p></div>
<div class="tabs" style="margin-top:26px">
<button class="tab" data-f="" data-on="1">전체 {len(TOPICS)}</button>{cattabs}
<span style="width:14px"></span>
<button class="tab" data-s="n" data-on="1">보도량순</button>
<button class="tab" data-s="o">의견 많은순</button>
<button class="tab" data-s="c">대립 강한순</button>
<button class="tab" data-s="last">최근 보도순</button>
<input class="field" type="search" id="q" placeholder="토픽 검색"></div>
<div class="grid" id="grid">{cards}</div>
<p id="empty" style="display:none;color:var(--ink-3);padding:40px 0">조건에 맞는 토픽이 없습니다.</p></div>"""
    js = """<script>
const grid=document.getElementById('grid'),cards=[...grid.children];
let cat='',sort='n',q='';
function apply(){let v=0;
 cards.forEach(c=>{const ok=(!cat||c.dataset.cat===cat)&&(!q||c.dataset.q.includes(q));
  c.style.display=ok?'':'none';if(ok)v++;});
 const s=[...cards].sort((a,b)=>sort==='last'?(a.dataset.last<b.dataset.last?1:-1)
   :parseFloat(b.dataset[sort])-parseFloat(a.dataset[sort]));
 s.forEach(c=>grid.appendChild(c));
 document.getElementById('empty').style.display=v?'none':'';}
document.querySelectorAll('[data-f]').forEach(b=>b.onclick=()=>{cat=b.dataset.f;
 document.querySelectorAll('[data-f]').forEach(x=>x.dataset.on=x===b?1:0);apply();});
document.querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{sort=b.dataset.s;
 document.querySelectorAll('[data-s]').forEach(x=>x.dataset.on=x===b?1:0);apply();});
document.getElementById('q').oninput=ev=>{q=ev.target.value.trim();apply();};
</script>"""
    page("topics.html", "토픽 — 갈피",
         f"국내 뉴스에서 정리한 {len(TOPICS)}개 토픽. 분야별로 걸러보고 보도량·의견 수·대립 강도로 정렬할 수 있습니다.",
         body, extra_js=js)


# ── 토픽 상세 ────────────────────────────────────────────
def build_topic(s):
    t = s["t"]
    order = {"찬성": 0, "반대": 1, "제기": 2}
    per = [sum(1 for a in t["articles"] if ART.get(a, {}).get("date") == d) for d in DATES]
    freq = Counter()
    for a in t["articles"]:
        freq.update(ART.get(a, {}).get("terms", []))
    kw = "".join(
        f'<a class="chip" href="../explore.html?w={e(w)}" style="color:{CC.get(A["cat"].get(w, t["cat"]), "#7C8899")}">'
        f'<span style="color:var(--ink-2)">{e(lb(w))}</span><b class="num">{n}</b></a>'
        for w, n in freq.most_common(12))
    ops = "".join(
        f'<div class="op {STK[o["stance"]]}"><div class="op-top">'
        f'<span class="pill {STK[o["stance"]]}">{o["stance"]}</span>'
        f'<span class="op-actor">{e(o["actor"])}</span></div>'
        f'<p class="op-text">{e(o["text"])}</p>'
        f'<div class="src-h">근거 기사 {len(o["articles"])}건</div>'
        + "".join(article_row(a) for a in o["articles"]) + "</div>"
        for o in sorted(t["opinions"], key=lambda o: order.get(o["stance"], 9)))
    arts = "".join(article_row(a) for a in sorted(t["articles"], key=lambda a: ART.get(a, {}).get("date", "")))
    others = [x for x in TOPICS if x["id"] != t["id"] and x["cat"] == t["cat"]][:4]
    oth = "".join(
        f'<a class="row-article" href="{x["id"]}.html"><span class="t" style="font-weight:600">'
        f'{e(x["label"])}</span><span class="num" style="font-size:11px;color:var(--ink-3)">'
        f'기사 {len(x["articles"])} · 의견 {len(x["opinions"])}</span></a>' for x in others)
    body = f"""<div class="wrap-narrow prose">
<div class="doc-head"><div style="display:flex;gap:10px;align-items:center">
<a href="../topics.html" style="font-size:12px;color:var(--ink-3);text-decoration:none">← 토픽 목록</a>
<span class="eyebrow" style="color:{CC[t["cat"]]}">{t["cat"]}</span></div>
<h1 class="doc-h1">{e(t["label"])}</h1><p class="doc-lead">{e(t["summary"])}</p>
<div class="doc-meta num"><span>기사 <b>{s["n"]}</b>건</span><span>의견 <b>{s["ops"]}</b>건</span>
<span>보도 기간 <b>{md(s["first"])} ~ {md(s["last"])}</b></span></div>
<div style="margin-top:16px;max-width:420px">{stancebar(s, "lg")}</div></div>

<h2>일자별 보도 분포</h2>{strip(per, CC[t["cat"]])}
<h2>제기된 의견 {len(t["opinions"])}건</h2>
<p class="sec-note">각 의견 아래에 그 발언이 실린 원문 기사가 붙어 있습니다. 인용은 기사 본문 표현을 그대로 옮긴 것입니다.</p>
{ops}
<h2>이 토픽의 기사 {len(t["articles"])}건</h2><div style="margin-top:12px">{arts}</div>
<h2>연결된 키워드</h2><p class="sec-note">누르면 네트워크 탐색기에서 해당 키워드가 선택된 상태로 열립니다</p>
<div class="chips">{kw}</div>
{'<h2>같은 분야의 다른 토픽</h2><div style="margin-top:10px">' + oth + '</div>' if oth else ''}
</div>"""
    NAV_PARENT[f"topics/{t['id']}.html"] = "topics.html"
    page(f"topics/{t['id']}.html", f"{t['label']} — 갈피", t["summary"], body, depth=1)


# ── 아카이브 ────────────────────────────────────────────
def build_archive():
    outlets = Counter(a["outlet"] for a in D["articles"])
    rows = "".join(
        f'<tr data-cat="{a["cat"]}" data-d="{a["date"]}" data-o="{e(a["outlet"])}" '
        f'data-q="{e(a["title"] + " " + " ".join(a["terms"]))}">'
        f'<td class="c-date num">{md(a["date"])}</td>'
        f'<td class="c-cat"><span class="cat-dot"><i style="background:{CC.get(a["cat"], "#7C8899")}"></i>{a["cat"]}</span></td>'
        f'<td class="c-outlet">{e(a["outlet"])}'
        + ('<br><span class="nofetch">링크만</span>' if is_nofetch(a["url"]) else '')
        + f'</td><td><a href="{e(a["url"])}" target="_blank" rel="noopener noreferrer">{e(a["title"])} '
          f'<span style="color:var(--ink-3)">↗</span></a></td></tr>'
        for a in sorted(D["articles"], key=lambda a: (a["date"], a["id"])))
    daytabs = "".join(
        f'<button class="tab num" data-d="{d}">{md(d)} ({wd(d)}) {META["daily"][i]}</button>'
        for i, d in enumerate(DATES))
    cattabs = "".join(
        f'<button class="tab" data-c="{c}">{c} {sum(1 for a in D["articles"] if a["cat"] == c)}</button>'
        for c in CATS if any(a["cat"] == c for a in D["articles"]))
    opts = "".join(f'<option value="{e(o)}">{e(o)} ({n})</option>' for o, n in outlets.most_common())
    body = f"""<div class="wrap">
<div style="padding:44px 0 8px"><h1 class="doc-h1" style="margin:0">기사 아카이브</h1>
<p class="doc-lead" style="max-width:62ch">분석에 사용한 {META["articles"]}건 전체입니다. 모든 행은 해당
언론사의 원문으로 연결됩니다. 사이트의 어떤 수치도 이 목록 밖에서 나오지 않습니다.
<span class="nofetch">링크만</span> 표시는 robots.txt에 따라 본문을 조회하지 않는 매체입니다.</p></div>
<div class="tabs" style="margin-top:24px"><button class="tab" data-d="" data-on="1">전체 기간</button>{daytabs}</div>
<div class="tabs"><button class="tab" data-c="" data-on="1">전체 분야</button>{cattabs}
<select class="field" id="ot"><option value="">전체 언론사 ({len(outlets)}곳)</option>{opts}</select>
<input class="field" type="search" id="q" placeholder="제목·키워드 검색"></div>
<p class="sec-note num" id="cnt"></p>
<table class="tbl"><thead><tr><th class="c-date">날짜</th><th class="c-cat">분야</th>
<th class="c-outlet">언론사</th><th>제목</th></tr></thead><tbody id="tb">{rows}</tbody></table>
<p id="empty" style="display:none;color:var(--ink-3);padding:40px 0">조건에 맞는 기사가 없습니다.</p></div>"""
    js = f"""<script>
const rs=[...document.getElementById('tb').children];let d='',c='',o='',q='';
function apply(){{let v=0;rs.forEach(r=>{{const ok=(!d||r.dataset.d===d)&&(!c||r.dataset.cat===c)
 &&(!o||r.dataset.o===o)&&(!q||r.dataset.q.includes(q));r.style.display=ok?'':'none';if(ok)v++;}});
 document.getElementById('cnt').textContent=v+'건 표시 중 (전체 {META["articles"]}건)';
 document.getElementById('empty').style.display=v?'none':'';}}
document.querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>{{d=b.dataset.d;
 document.querySelectorAll('[data-d]').forEach(x=>x.dataset.on=x===b?1:0);apply();}});
document.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>{{c=b.dataset.c;
 document.querySelectorAll('[data-c]').forEach(x=>x.dataset.on=x===b?1:0);apply();}});
document.getElementById('ot').onchange=ev=>{{o=ev.target.value;apply();}};
document.getElementById('q').oninput=ev=>{{q=ev.target.value.trim();apply();}};
apply();</script>"""
    page("archive.html", "기사 아카이브 — 갈피",
         f"분석에 사용한 국내 기사 {META['articles']}건 전체 목록. 날짜·분야·언론사로 걸러보고 원문으로 바로 이동할 수 있습니다.",
         body, extra_js=js)


# ── 문서 페이지 ────────────────────────────────────────
def build_docs():
    outlets = len({a["outlet"] for a in D["articles"]})
    rng = f'{META["range"][0].replace("-", "년 ", 1).replace("-", "월 ")}일부터 {META["range"][1].replace("-", "년 ", 1).replace("-", "월 ")}일까지'
    m = C.METHOD.format(
        RANGE_TEXT=rng, OUTLETS=outlets, ARTICLES=META["articles"],
        DAILY_TEXT=" · ".join(f"{md(d)}({wd(d)}) {META['daily'][i]}건" for i, d in enumerate(DATES)),
        VOCAB=META["vocab"], TOPICS=META["topics"], OPINIONS=META["opinions"])
    page("method.html", "분석 방법 — 갈피",
         "키워드 태깅, 파이(φ) 상관계수, 네트워크 배치, 부상·소멸 지표까지 이 사이트의 수치가 만들어진 과정과 한계를 밝힙니다.",
         f'<div class="wrap-narrow prose"><div style="padding:44px 0 0">{m}</div></div>')

    p = C.POLICY.format(T_BLOCKED=table(C.BLOCKED), T_PARTIAL=table(C.PARTIAL),
                        T_PENDING=table(C.PENDING), OPEN_LIST=" · ".join(C.OPEN_LIST))
    page("policy.html", "이용 정책과 저작권 — 갈피",
         "인용 원칙, 링크 정책, 언론사 robots.txt 전수 확인 결과, 삭제 요청 창구를 공개합니다.",
         f'<div class="wrap-narrow prose"><div style="padding:44px 0 0">{p}</div></div>')


# ── 탐색기 ────────────────────────────────────────────
DARK2LIGHT = [
    ("--bg:#0e1117", "--bg:#f4f5f7"), ("--panel:#161b25", "--panel:#ffffff"),
    ("--panel2:#1d2431", "--panel2:#f4f5f7"), ("--line:#2a3444", "--line:#dfe3e9"),
    ("--line2:#3d4c63", "--line2:#b9c1cd"), ("--tx:#e7ecf3", "--tx:#12161c"),
    ("--tx2:#9aa7b8", "--tx2:#4a5462"), ("--tx3:#66738a", "--tx3:#7c8899"),
    ("--pro:#4bbf9e", "--pro:#0b7a5e"), ("--con:#e4707f", "--con:#b3323f"),
    ("--neu:#e0a94a", "--neu:#a96a0b"), ("--acc:#7c9cf5", "--acc:#2f4bc4"),
    ("background:#121722", "background:#ffffff"),
    ("fill:#39465a", "fill:#c8cfd9"), ("fill:#8fa9e8", "fill:#6d86dd"),
    ("fill:#b9caf8", "fill:#2f4bc4"),
    ("background:#212a38", "background:#f4f5f7"),
    ("background:#141a24", "background:#ffffff"),
    ("background:#18202c", "background:#f4f5f7"),
    ("background:#222b38", "background:#eceff3"),
    ("background:#2a3444", "background:#cfd6df"),
    ("stroke:#3a4759", "stroke:#9aa5b4"), ("stroke:#8aa4d8", "stroke:#2f4bc4"),
    ("rgba(22,27,37,.85)", "rgba(255,255,255,.92)"),
    ("rgba(22,27,37,.82)", "rgba(255,255,255,.92)"),
    ("rgba(124,156,245,.15)", "rgba(47,75,196,.10)"),
    ("color:#b9caf8", "color:#2f4bc4"),
    ("color:#cdd6e3", "color:#12161c"),
    ("#2b3446", "#dfe3e9"), ("#2b3span", "#dfe3e9"),
    ('stroke:#fff; stroke-width:2.5', 'stroke:#12161c; stroke-width:2.5'),
    ('CC = {정치:"#7c9cf5",경제:"#4bbf9e",사회:"#f0a352",국제:"#c98bdb",문화:"#e4707f",스포츠:"#63c5da"}',
     'CC = {정치:"#3B5BDB",경제:"#0B7A5E",사회:"#C2410C",국제:"#6D3FC4",문화:"#C2255C",스포츠:"#0C7C99"}'),
]


# ── 오늘의 낱말 ──────────────────────────────────────────
# 게임의 정답은 "전일 뉴스에 가장 많이 등장한 키워드"다. 조건은 셋이다.
#   ① 2음절            ② 게임 사전(83,091개)에 실재  ③ 자모 4~7칸
# 같은 단어가 며칠씩 반복되면 게임이 죽으므로 최근에 쓴 말은 건너뛴다.
#
# 다만 2음절 적격 키워드는 수가 적어서(현재 18개) 28일을 딱 잘라 적용하면
# 뉴스 키워드를 쓸 수 있는 날에도 무관한 일반 단어가 나가 버린다. 그래서 텀을
# 단계적으로 완화한다 — 28일을 목표로 하되, 안 되면 14 → 7 → 무제한 순으로 물러선다.
# 뉴스와 무관한 단어를 내는 것보다 조금 일찍 반복하는 편이 서비스 취지에 맞다.
# 어느 단계에서도 못 고르면 그때만 일반 정답 풀로 넘기고, 그 사실을 화면에 밝힌다.
REPEAT_GAPS = [28, 14, 7, 0]

_CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
_JUNG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
_JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ",
         "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
_SPLIT = {"ㄲ": "ㄱㄱ", "ㄸ": "ㄷㄷ", "ㅃ": "ㅂㅂ", "ㅆ": "ㅅㅅ", "ㅉ": "ㅈㅈ",
          "ㄳ": "ㄱㅅ", "ㄵ": "ㄴㅈ", "ㄶ": "ㄴㅎ", "ㄺ": "ㄹㄱ", "ㄻ": "ㄹㅁ", "ㄼ": "ㄹㅂ",
          "ㄽ": "ㄹㅅ", "ㄾ": "ㄹㅌ", "ㄿ": "ㄹㅍ", "ㅀ": "ㄹㅎ", "ㅄ": "ㅂㅅ",
          "ㅘ": "ㅗㅏ", "ㅙ": "ㅗㅐ", "ㅚ": "ㅗㅣ", "ㅝ": "ㅜㅓ", "ㅞ": "ㅜㅔ", "ㅟ": "ㅜㅣ", "ㅢ": "ㅡㅣ"}


def jamo_len(w):
    """두벌식 홑자모로 분해했을 때의 칸 수. 완성형이 아니면 None."""
    out = []
    for ch in w:
        c = ord(ch) - 0xAC00
        if not 0 <= c < 11172:
            return None
        for x in (_CHO[c // 588], _JUNG[(c % 588) // 28], _JONG[c % 28]):
            if x:
                out.append(_SPLIT.get(x, x))
    return len("".join(out))


def next_day(d):
    y, m, dd = (int(x) for x in d.split("-"))
    days = [31, 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    dd += 1
    if dd > days[m - 1]:
        dd, m = 1, m + 1
        if m > 12:
            m, y = 1, y + 1
    return f"{y:04d}-{m:02d}-{dd:02d}"


def game_words():
    """게임 템플릿에 박혀 있는 단어 목록을 그대로 읽어 온다(중복 관리 지점 제거)."""
    src = open(os.path.join(ROOT, "game.tpl.html"), encoding="utf-8").read()
    i = src.index("const WORDS_RAW = ") + len("const WORDS_RAW = ")
    raw, _ = json.JSONDecoder().raw_decode(src[i:])
    pair = lambda t: {t[k:k + 2] for k in range(0, len(t), 2)}
    return pair(raw["all"]), pair(raw["answers"])


def build_puzzles(allw, answers):
    """플레이 날짜 → 퍼즐. D일 기사에서 뽑아 D+1일에 낸다."""
    eligible = [w for w in TREND
                if len(w) == 2 and w in allw and (jamo_len(w) or 0) in (4, 5, 6, 7)]
    puzzles, used = {}, []
    for i, d in enumerate(DATES):
        play = next_day(d)
        ranked = sorted(((TREND[w][i], w) for w in eligible if TREND[w][i] > 0),
                        key=lambda r: (-r[0], r[1]))
        pick = None
        for gap in REPEAT_GAPS:
            recent = used[-gap:] if gap else []
            pick = next((r for r in ranked if r[1] not in recent), None)
            if pick:
                break
        if pick:
            n, w = pick
            tps = [t for t in TOPICS
                   if any(w in ART[a]["terms"] for a in t["articles"] if a in ART)][:5]
            puzzles[play] = {"w": w, "src": d, "n": n, "fb": False,
                             "topics": [{"id": t["id"], "label": t["label"], "cat": t["cat"]}
                                        for t in tps]}
            used.append(w)
        else:
            # 조건에 맞는 새 키워드가 없는 날. 일반 정답 풀로 넘기고 화면에 밝힌다.
            pool = sorted(answers)
            h = 2166136261
            for ch in play:
                h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
            puzzles[play] = {"w": pool[h % len(pool)], "src": d, "n": 0,
                             "fb": True, "topics": []}
    return puzzles


def build_game():
    allw, answers = game_words()
    puzzles = build_puzzles(allw, answers)
    latest = max(puzzles) if puzzles else ""
    payload = {"latest": latest, "puzzles": puzzles}
    tpl = open(os.path.join(ROOT, "game.tpl.html"), encoding="utf-8").read()
    tpl = tpl.replace("__NAV__", nav("game.html"))
    tpl = tpl.replace("__DAILY__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    open(os.path.join(OUT, "game.html"), "w", encoding="utf-8").write(tpl)
    real = sum(1 for p in puzzles.values() if not p["fb"])
    return len(puzzles), real


def build_explore():
    tpl = open(os.path.join(ROOT, "explore.tpl.html"), encoding="utf-8").read()
    for a, b in DARK2LIGHT:
        tpl = tpl.replace(a, b)
    d3 = open(os.path.join(ROOT, "vendor", "d3.min.js"), encoding="utf-8").read()
    tpl = tpl.replace("__D3__", d3)
    tpl = tpl.replace("__DATA__", json.dumps(D, ensure_ascii=False, separators=(",", ":")))
    tpl = tpl.replace("__NAV__", nav("explore.html"))
    open(os.path.join(OUT, "explore.html"), "w", encoding="utf-8").write(tpl)


# ── 실행 ────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in STATS:
        build_topic(s)
    build_index()
    build_topics()
    build_archive()
    build_docs()
    build_explore()
    n_puz, n_real = build_game()
    shutil.copy(DATA_PATH, os.path.join(OUT, "data.json"))

    # 정적 자산(site.css, favicon.svg, cover.png)을 public/assets 로 복사한다.
    # public/ 은 .gitignore 대상이므로 원본은 반드시 저장소의 assets/ 에 있어야 한다.
    src_assets = os.path.join(ROOT, "assets")
    if not os.path.isdir(src_assets):
        raise SystemExit("assets/ 폴더가 없습니다. site.css·favicon.svg·cover.png 가 저장소에 있어야 합니다.")
    shutil.copytree(src_assets, os.path.join(OUT, "assets"), dirs_exist_ok=True)
    missing = [f for f in ("site.css", "favicon.svg", "cover.png")
               if not os.path.isfile(os.path.join(OUT, "assets", f))]
    if missing:
        raise SystemExit("assets/ 에 다음 파일이 없습니다: " + ", ".join(missing))

    n = sum(len(f) for _, _, f in os.walk(OUT))
    print(f"생성 완료 — {n}개 파일")
    print(f"  기사 {META['articles']} · 토픽 {META['topics']} · 의견 {META['opinions']} · 키워드 {len(A['terms'])}")
    _m = len(A["terms"]) * (len(A["terms"]) - 1) // 2
    _co = min((n11 for *_r, n11, p in A["links"]), default=0)
    _ph = min((phi for _x, _y, phi, _n, _p in A["links"]), default=0)
    _nd = len({t for x, y, *_r in A["links"] for t in (x, y)})
    print(f"  연결: {len(A['links'])}개 유의 · 단어 {_nd}개 (조합 {_m}쌍 · 공동등장 {MIN_CO}건 이상"
          f" · FDR {Q_FDR}) · 최소 근거 {_co}건 · 최소 φ {_ph:.3f}")
    print(f"  본문 미조회 매체 기사: {sum(1 for a in D['articles'] if is_nofetch(a['url']))}건")
    print(f"  오늘의 낱말: {n_puz}일치 (뉴스 키워드 {n_real} · 일반 단어 폴백 {n_puz - n_real})")

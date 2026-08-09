#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jamowordle.html → game.tpl.html 변환기 (1회성).

원본 자모 워들 MVP를 갈피 사이트의 한 페이지로 이식한다.
  · 갈피 네비 주입 지점(__NAV__) 추가
  · 다크/보라 팔레트를 갈피 라이트 팔레트로 교체
  · 정답을 갈피 전일 키워드에서 받도록 pickAnswer 교체(__DAILY__)
  · 정답 공개 시 그 단어의 토픽·네트워크로 연결
"""
import os
import re
import sys

SRC = sys.argv[1]
DST = sys.argv[2]
s = open(SRC, encoding="utf-8").read()


def sub1(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f"[실패] 치환 대상 없음: {label}")
    s = s.replace(old, new, 1)


# ── 1. head ────────────────────────────────────────────
sub1("<title>자모 워들 — 한글 Wordle</title>",
     '<title>오늘의 낱말 — 갈피</title>\n'
     '<meta name="description" content="어제 뉴스에 가장 많이 등장한 단어를 자모 여섯 번으로 맞혀 보세요. 갈피의 키워드 분석에서 뽑은 오늘의 낱말.">\n'
     '<meta property="og:title" content="오늘의 낱말 — 갈피">\n'
     '<meta property="og:description" content="어제 뉴스에 가장 많이 등장한 단어를 자모 여섯 번으로 맞혀 보세요.">\n'
     '<meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image">\n'
     '<meta property="og:image" content="assets/cover.png">\n'
     '<link rel="icon" href="assets/favicon.svg">',
     "title")

# ── 1b. 외부 폰트 제거 ──────────────────────────────────
# 갈피의 다른 페이지는 시스템 폰트만 쓴다(외부 요청 0). 게임만 구글 폰트를 부르면
# 일관성도 깨지고, 이용 정책에서 밝힌 "외부로 아무것도 보내지 않는다"와도 어긋난다.
sub1('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
     '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
     '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">\n',
     "", "구글 폰트 제거")

# ── 2. 팔레트 — 갈피 라이트 ─────────────────────────────
sub1(
    "  --bg:#ffffff; --fg:#1a1a1b; --sub:#787c7e; --line:#d3d6da; --tile-empty:#ffffff;\n"
    "  --key:#d3d6da; --key-fg:#1a1a1b; --accent:#6d28d9;\n"
    "  --correct:#6aaa64; --present:#c9b458; --absent:#787c7e; --panel:#ffffff;",
    "  --bg:#f4f5f7; --fg:#12161c; --sub:#7c8899; --line:#dfe3e9; --tile-empty:#ffffff;\n"
    "  --key:#e7eaef; --key-fg:#12161c; --accent:#2f4bc4;\n"
    "  --correct:#0b7a5e; --present:#a96a0b; --absent:#7c8899; --panel:#ffffff;",
    "라이트 팔레트")

sub1(
    "  --bg:#121213; --fg:#f8f8f8; --sub:#8d8f92; --line:#3a3a3c; --tile-empty:#121213;\n"
    "  --key:#818384; --key-fg:#f8f8f8; --accent:#a78bfa;\n"
    "  --correct:#538d4e; --present:#b59f3b; --absent:#3a3a3c; --panel:#1e1e20;",
    "  --bg:#12161c; --fg:#eef1f5; --sub:#8b97a6; --line:#2a323c; --tile-empty:#12161c;\n"
    "  --key:#3a434f; --key-fg:#eef1f5; --accent:#8ea2ff;\n"
    "  --correct:#0f9d78; --present:#c98a20; --absent:#3a434f; --panel:#1a2029;",
    "다크 팔레트")

# 폰트: 갈피 본문과 맞춤(Pretendard 우선, 없으면 기존 폴백)
sub1("font-family:'Noto Sans KR',-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;",
     'font-family:"Pretendard",-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","맑은 고딕",sans-serif;',
     "폰트")

# ── 2b. 모음 키 표시색을 갈피 accent 로 ──────────────────
sub1(".key.vowel{box-shadow:inset 0 -3px 0 rgba(109,40,217,.35)}",
     ".key.vowel{box-shadow:inset 0 -3px 0 rgba(47,75,196,.32)}", "모음 키 라이트")
sub1('html[data-theme="dark"] .key.vowel{box-shadow:inset 0 -3px 0 rgba(167,139,250,.5)}',
     'html[data-theme="dark"] .key.vowel{box-shadow:inset 0 -3px 0 rgba(142,162,255,.5)}', "모음 키 다크")

# ── 2c. 좁은 화면에서 자판 넘침 ─────────────────────────
# 첫 줄이 12키다. 390px 기기에서 min-width 30 + gap 4 이면 404px 라 잘린다.
sub1("@media (max-width:400px){ .key{height:48px;font-size:15px} }",
     "@media (max-width:430px){ .key{height:48px;font-size:15px;min-width:24px}\n"
     "  .krow{gap:3px} .key.wide{min-width:42px;font-size:11px} #keyboard{padding:6px 3px 10px} }\n"
     "@media (max-width:340px){ .key{min-width:20px;font-size:14px} .krow{gap:2px} }",
     "좁은 화면 자판")

# ── 3. 갈피 네비 CSS + 게임 전용 추가 ───────────────────
NAV_CSS = """
/* ── 갈피 공유 네비 ── */
.nav{flex:0 0 auto;display:flex;align-items:center;gap:26px;padding:0 20px;height:56px;
  background:rgba(244,245,247,.93);border-bottom:1px solid var(--line)}
html[data-theme="dark"] .nav{background:rgba(18,22,28,.93)}
.nav-mark{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--fg);flex:0 0 auto}
.nav-mark b{font-size:14.5px;font-weight:800;letter-spacing:-.035em}
.nav-links{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}
.nav-links::-webkit-scrollbar{display:none}
.nav-link{position:relative;padding:6px 11px;font-size:13px;color:var(--sub);text-decoration:none;border-radius:6px;white-space:nowrap}
.nav-link:hover{color:var(--fg)}
.nav-link[data-on="1"]{color:var(--fg);font-weight:700}
.nav-link[data-on="1"]::after{content:"";position:absolute;left:11px;right:11px;bottom:-1px;height:2px;background:var(--accent)}
.nav-span{margin-left:auto;font-size:11.5px;color:var(--sub);white-space:nowrap}
@media(max-width:620px){.nav{gap:12px;padding:0 12px}.nav-span{display:none}}

/* ── 오늘의 낱말: 출처 배지 ── */
#src{font-size:12px;color:var(--sub);text-align:center;line-height:1.6;max-width:42ch;word-break:keep-all;padding:0 12px}
#src b{color:var(--accent);font-weight:700}
#src .q{display:block;margin-top:3px}

/* ── 정답 공개 후 갈피 연결 ── */
#link{margin-top:14px;padding:13px 14px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}
#link h4{margin:0 0 8px;font-size:12px;color:var(--sub);font-weight:600;letter-spacing:.02em}
#link a{display:block;padding:7px 0;font-size:13.5px;color:var(--fg);text-decoration:none;border-bottom:1px solid var(--line)}
#link a:last-child{border-bottom:0}
#link a:hover{color:var(--accent)}
#link .cat{font-size:11px;color:var(--sub);margin-left:6px}
#link .go{color:var(--accent);font-weight:600}
</style>"""
sub1("</style>", NAV_CSS, "네비 CSS")

# ── 4. 헤더 교체 ───────────────────────────────────────
sub1("""<header>
  <div class="brand">자모<span>워들</span></div>
  <div class="hbtns">""",
     """__NAV__

<header>
  <div class="brand">오늘의 낱말</div>
  <div class="hbtns">""",
     "헤더")

# ── 5. 출처 배지 자리 ──────────────────────────────────
sub1('<div id="meta"></div>', '<div id="meta"></div>\n  <div id="src"></div>', "출처 배지")

# ── 6. 정답 박스 아래 연결 패널 자리 ────────────────────
sub1('<div id="answerBox"></div>', '<div id="answerBox"></div>\n  <div id="link"></div>', "연결 패널")

# ── 7. 갈피 데이터 + 정답 선택 교체 ─────────────────────
sub1("""function pickAnswer(){
  let pool;
  if (opts.len && BY_LEN[opts.len]) pool = BY_LEN[opts.len];
  else pool = WORDS.answers;
  if (opts.mode === 'daily'){
    const d = new Date();
    const key = d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate()+'-'+(opts.len||'x');
    return pool[dailyIndex(key, pool.length)];
  }
  return pool[Math.floor(Math.random() * pool.length)];
}""",
     """/* ---------- 갈피 연동 ---------- */
// build.py 가 data.json 에서 만들어 넣는다.
// { latest, puzzles: { "<플레이 날짜>": {w, src, n, fb, topics:[{id,label,cat}]} } }
const GALPI = __DAILY__;

function todayKST(){
  const now = new Date();
  const kst = new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + (9 * 3600000));
  const p = (x) => String(x).padStart(2, '0');
  return kst.getFullYear() + '-' + p(kst.getMonth() + 1) + '-' + p(kst.getDate());
}

// 오늘 날짜의 퍼즐. 아직 안 만들어졌으면(사이트가 하루 뒤처졌으면) 가장 최근 것.
function todayPuzzle(){
  return GALPI.puzzles[todayKST()] || GALPI.puzzles[GALPI.latest] || null;
}

function pickAnswer(){
  if (opts.mode === 'daily'){
    const p = todayPuzzle();
    if (p && DICT_SET.has(p.w)) return p.w;       // 갈피 키워드
    // 폴백: 날짜 시드로 일반 정답 풀에서
    return WORDS.answers[dailyIndex(todayKST(), WORDS.answers.length)];
  }
  const pool = (opts.len && BY_LEN[opts.len]) ? BY_LEN[opts.len] : WORDS.answers;
  return pool[Math.floor(Math.random() * pool.length)];
}""",
     "pickAnswer")

# ── 8. 출처 문구 렌더 ──────────────────────────────────
sub1("""function updateMeta(){
  const n = G.jamo.length;
  $('#meta').innerHTML = `2글자 단어 · 자모 <b>${n}칸</b> · ${MAX_TRY}번의 기회` +
    (opts.mode==='daily' ? ' · 오늘의 단어' : ' · 무한 모드') +
    (opts.hard ? ' · 하드' : '');
}""",
     """function updateMeta(){
  const n = G.jamo.length;
  $('#meta').innerHTML = `2글자 단어 · 자모 <b>${n}칸</b> · ${MAX_TRY}번의 기회` +
    (opts.mode==='daily' ? ' · 오늘의 낱말' : ' · 무한 모드') +
    (opts.hard ? ' · 하드' : '');
  renderSrc();
}

// 오늘의 낱말이 어디서 왔는지 알려 준다. 정답을 노출하지 않는 선에서만.
function renderSrc(){
  const el = $('#src');
  if (opts.mode !== 'daily'){ el.innerHTML = ''; return; }
  const p = todayPuzzle();
  if (!p){ el.innerHTML = ''; return; }
  if (p.fb){
    el.innerHTML = '<span class="q">어제 뉴스에서 조건에 맞는 새 키워드가 없어 일반 단어로 냅니다.</span>';
    return;
  }
  const [mm, dd] = p.src.slice(5).split('-');
  const d = Number(mm) + '월 ' + Number(dd) + '일';
  el.innerHTML = `<b>${d}</b> 뉴스에 가장 많이 등장한 단어입니다` +
    `<span class="q">기사 ${p.n}건에 나왔어요</span>`;
}""",
     "updateMeta")

# ── 9. 정답 공개 시 갈피로 연결 ─────────────────────────
sub1("""  $('#answerBox').innerHTML = G.done
    ? `<h3>정답</h3><p style="font-size:20px;font-weight:700;margin:0">${G.answer}
       <span style="font-size:13px;color:var(--sub);font-weight:400"> (${G.jamo.join(' ')})</span></p>` : '';""",
     """  $('#answerBox').innerHTML = G.done
    ? `<h3>정답</h3><p style="font-size:20px;font-weight:700;margin:0">${G.answer}
       <span style="font-size:13px;color:var(--sub);font-weight:400"> (${G.jamo.join(' ')})</span></p>` : '';
  renderLink();""",
     "answerBox")

sub1("""function shareText(){""",
     """// 정답이 공개된 뒤에만, 그 단어가 실제 뉴스에서 어떻게 쓰였는지로 이어 준다.
function renderLink(){
  const el = $('#link');
  const p = todayPuzzle();
  if (!G.done || opts.mode !== 'daily' || !p || p.fb || p.w !== G.answer){
    el.innerHTML = ''; return;
  }
  const rows = (p.topics || []).map(t =>
    `<a href="topics/${t.id}.html">${t.label}<span class="cat">${t.cat}</span></a>`).join('');
  el.innerHTML =
    `<h4>'${G.answer}' 이(가) 나온 뉴스</h4>${rows}` +
    `<a class="go" href="explore.html?w=${encodeURIComponent(G.answer)}">네트워크에서 '${G.answer}' 보기 →</a>`;
}

function shareText(){""",
     "renderLink")

# ── 10. 공유 문구 ──────────────────────────────────────
s = s.replace("자모워들", "갈피 오늘의 낱말")

# 남은 브랜드 흔적
s = re.sub(r"자모\s*워들", "오늘의 낱말", s)

open(DST, "w", encoding="utf-8").write(s)
print(f"생성: {DST}  ({len(s):,} bytes)")
for ph in ("__NAV__", "__DAILY__"):
    print(f"  {ph}: {s.count(ph)}개")

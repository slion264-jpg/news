# 이슈 네트워크 — 배포 안내

기간별 뉴스 상관 분석 사이트. **빌드 의존성이 없습니다** — Python 3만 있으면 됩니다.
React, Node, 번들러, 패키지 설치 모두 필요 없습니다.

| 항목 | 값 |
|---|---|
| Firebase 프로젝트 | `news-e86be` |
| 배포 주소 | `https://news-e86be.web.app` · `https://news-e86be.firebaseapp.com` |
| GitHub 저장소 | `https://github.com/slion264-jpg/news.git` |

```
build.py           생성기. data.json → public/*.html
content.py         분석 방법 · 이용 정책 본문, 수집 제외 도메인 목록
data.json          단 하나의 데이터 소스 (기사·토픽·의견)
explore.tpl.html   네트워크 탐색기 템플릿
vendor/d3.min.js   탐색기용 D3 (ISC License)
setup.sh           최초 1회 설정 스크립트
public/            ← 생성 결과. .gitignore 처리돼 있고 CI가 매번 다시 만듭니다
```

## 빠른 길 — 스크립트 한 번

```bash
./setup.sh
```

빌드 → Firebase 로그인 → 배포 → GitHub push까지 한 번에 합니다.
중간에 브라우저 로그인 창이 뜹니다. 아래는 같은 일을 손으로 하는 방법입니다.

## 1. 로컬에서 확인

```bash
python3 build.py
python3 -m http.server 8000 --directory public
# http://localhost:8000
```

58개 파일(홈, 탐색기, 토픽 목록, 토픽 상세 48개, 아카이브, 분석 방법, 이용 정책)이 만들어집니다.
데이터가 바뀌면 이 명령만 다시 돌리면 됩니다.

## 2. Firebase Hosting 첫 배포

프로젝트 `news-e86be`는 이미 `.firebaserc`에 설정돼 있습니다.
Firebase 콘솔에서 **빌드 → Hosting → 시작하기**를 한 번 눌러 Hosting을 활성화해 두세요.

```bash
npm install -g firebase-tools
firebase login
python3 build.py
firebase deploy --only hosting
```

끝나면 `https://news-e86be.web.app` 이 열립니다.
원하는 도메인이 있으면 Hosting → **맞춤 도메인 추가**에서 연결할 수 있고 인증서는 자동 발급됩니다.

## 3. GitHub 연결

```bash
git init -b main
git add -A
git commit -m "이슈 네트워크 — 정적 사이트"
git remote add origin https://github.com/slion264-jpg/news.git
git push -u origin main
```

## 4. 자동 배포 켜기

```bash
firebase init hosting:github
```

저장소를 물으면 `slion264-jpg/news`를 지정합니다. 이 명령이 서비스 계정을 만들고
**`FIREBASE_SERVICE_ACCOUNT_NEWS_E86BE`** 시크릿을 저장소에 자동 등록합니다.
`.github/workflows/deploy.yml`이 정확히 이 이름을 참조하고 있으므로 추가 설정은 없습니다.

> 명령이 워크플로 파일을 새로 만들겠다고 물으면 **거절하세요.** 이미 들어 있습니다.
> (덮어썼다면 이 번들의 `deploy.yml`로 되돌리면 됩니다.)

직접 하시려면: Firebase 콘솔 → 프로젝트 설정 → 서비스 계정 → **새 비공개 키 생성**으로 받은
JSON 전체를 GitHub 저장소 → Settings → Secrets and variables → Actions 에
위 이름으로 등록하면 됩니다.

이후 `main`에 push할 때마다 GitHub가 `build.py`를 돌려 Firebase에 올립니다.
Actions 탭에서 결과를 볼 수 있습니다.

## 5. 데이터 갱신 흐름

갱신은 **`data.json` 하나만 바꾸면** 됩니다. 나머지는 전부 생성물입니다.

데이터는 **롤링 삭제 없이 계속 누적**합니다. 이용자가 사이트에서 기간을 직접 고르기 때문에
과거 날짜를 지울 이유가 없습니다. 현재 2026-07-30 ~ 2026-08-09, 11일치 232건입니다.

```
data.json 교체 → git push → GitHub Actions가 build.py 실행 → Firebase 배포
```

매일 오전 7시 예약 작업이 전날 뉴스를 수집해 갱신된 `data.json`을 보내 드립니다.
받은 파일을 이 폴더에 덮어쓰고 push하면 끝입니다.

```bash
git add data.json && git commit -m "8월 8일자 갱신" && git push
```

`data.json` 구조:

```jsonc
{
  "meta":   { "range", "dates", "daily", "articles", "topics", "opinions", "vocab" },
  "label":  { "종합부동산세": "종부세", ... },   // 화면 표기용 별칭
  "trend":  { "폭염": [0,1,2,3,4,5,6], ... },    // 단어별 일자 등장 수, 길이 = dates 길이
  "articles": [ { "id","date","outlet","title","url","cat","terms":[] } ],
  "topics":   [ { "id","label","cat","summary","articles":[],
                  "opinions":[ { "stance","actor","text","articles":[] } ] } ]
}
```

- `cat` — 정치 · 경제 · 사회 · 국제 · 문화 · 스포츠
- `stance` — 찬성 · 반대 · 제기
- 모든 `topics[].articles`와 `opinions[].articles`의 id는 `articles`에 실재해야 합니다

## 6. 수집 정책이 코드에 박혀 있는 곳

`content.py`의 **`NO_FETCH_DOMAINS`** — robots.txt에서 Claude 계열 크롤러를 차단한 매체입니다.
이 목록의 도메인은 **본문을 조회하지 않고** 제목·링크만 씁니다. 기사 목록과 아카이브에
`링크만` 배지로 표시됩니다.

```python
NO_FETCH_DOMAINS = [
  "khan.co.kr", "sports.khan.co.kr", "weekly.khan.co.kr", "nocutnews.co.kr",
  "sedaily.com", "kmib.co.kr", "imnews.imbc.com", "asiae.co.kr",
]
```

매체가 정책을 바꾸거나 제외를 요청하면 이 목록만 고치면 사이트 전체에 반영됩니다.
배경은 배포된 사이트의 **이용 정책** 페이지에 있습니다.

## 7. 알아 두실 것

- `public/`은 `.gitignore`에 있습니다. 로컬에서 `firebase deploy` 하려면 먼저 `build.py`를 돌리세요.
- 탐색기(`explore.html`)는 데이터를 인라인으로 품고 있어 약 400KB입니다. 나머지 페이지는 가볍습니다.
- 서버가 없는 정적 파일뿐이라 Firebase Hosting 무료 한도로 충분합니다.
- `vendor/d3.min.js`는 ISC 라이선스이며 저작권 표기가 파일에 포함돼 있습니다.

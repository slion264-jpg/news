#!/usr/bin/env bash
# 갈피 — 최초 1회 설정. 이 폴더에서 실행하세요.
set -e
echo "▶ 1/4  정적 사이트 생성"
python3 build.py

echo "▶ 2/4  Firebase CLI 확인"
command -v firebase >/dev/null || npm install -g firebase-tools
firebase login --no-localhost || firebase login

echo "▶ 3/4  Firebase Hosting 배포 (news-e86be)"
firebase deploy --only hosting --project news-e86be

echo "▶ 4/4  GitHub 연결"
git init -b main 2>/dev/null || true
git add -A
git commit -m "갈피 — 정적 사이트" || true
git remote add origin https://github.com/slion264-jpg/news.git 2>/dev/null || \
  git remote set-url origin https://github.com/slion264-jpg/news.git
git push -u origin main

echo
echo "완료. 이제 firebase init hosting:github 을 실행해 자동 배포를 연결하세요."
echo "  → 저장소는 slion264-jpg/news 를 지정하면 됩니다."

#!/usr/bin/env bash
# cron이 이 파일 하나만 부르게 하는 래퍼. .env 로드 후 실행.
cd "$(dirname "$0")" || exit 1
[ -f .env ] && . ./.env
venv/bin/python3 news_digest.py

#!/usr/bin/env python3
"""
korea-daily-news-digest (무료 버전)
- Google News(한국) RSS로 뉴스 수집 → 주제별로 정리 → 텔레그램/파일 전달
- Claude API 미사용 = 과금 없음. (LLM 요약 대신 헤드라인 목록 정리)

필요 패키지:  pip install feedparser requests
환경변수(.env):
  TELEGRAM_BOT_TOKEN  (선택 - 있으면 텔레그램 전송)
  TELEGRAM_CHAT_ID    (선택)
  NEWS_KEYWORDS       (선택 - 쉼표구분. 비우면 종합 헤드라인)
                      예: "코스피,비트코인,인디게임"
  MAX_PER_TOPIC       (선택 - 주제당 기사 수, 기본 5)
"""

import os
import sys
import html
import datetime
from collections import OrderedDict

import feedparser
import requests

# ---------- 설정 ----------
GNEWS_BASE = "https://news.google.com/rss"
LOCALE = "hl=ko&gl=KR&ceid=KR:ko"
OUT_DIR = os.path.expanduser("~/korea-daily-news-digest/archive")


# ---------- 1. 뉴스 수집 ----------
def fetch_news():
    max_per = int(os.getenv("MAX_PER_TOPIC", "5"))
    keywords = [k.strip() for k in os.getenv("NEWS_KEYWORDS", "").split(",") if k.strip()]

    topics = keywords if keywords else ["주요뉴스"]
    groups = OrderedDict()

    for topic in topics:
        if topic == "주요뉴스":
            url = f"{GNEWS_BASE}?{LOCALE}"
        else:
            url = f"{GNEWS_BASE}/search?q={requests.utils.quote(topic)}&{LOCALE}"

        feed = feedparser.parse(url)
        items, seen = [], set()
        for e in feed.entries:
            title = html.unescape(getattr(e, "title", "")).strip()
            if not title or title in seen:
                continue
            seen.add(title)
            src = e["source"].get("title", "") if e.get("source") else ""
            clean = title.rsplit(" - ", 1)[0] if src and title.endswith(f" - {src}") else title
            items.append({"title": clean, "source": src, "link": getattr(e, "link", "")})
            if len(items) >= max_per:
                break
        if items:
            groups[topic] = items

    return groups


# ---------- 2. 정리 (LLM 없이 포맷팅만) ----------
def build_digest(groups):
    if not groups:
        return "오늘 수집된 뉴스가 없습니다."
    lines = []
    for topic, items in groups.items():
        lines.append(f"\n■ {topic}")
        for a in items:
            src = f" ({a['source']})" if a["source"] else ""
            lines.append(f"  · {a['title']}{src}")
            if a["link"]:
                lines.append(f"    {a['link']}")
    return "\n".join(lines).strip()


# ---------- 3. 전달 ----------
def deliver(text):
    today = datetime.date.today().isoformat()
    body = f"📰 오늘의 뉴스 ({today})\n{text}"

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        for chunk in [body[i:i + 3800] for i in range(0, len(body), 3800)]:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=30,
            )
            r.raise_for_status()
        print(f"[OK] 텔레그램 전송 완료 · 백업: {path}")
    else:
        print(f"[OK] 파일 저장: {path}  (텔레그램 미설정 → 전송 생략)")
        print("\n" + body)


def main():
    try:
        groups = fetch_news()
        total = sum(len(v) for v in groups.values())
        print(f"[INFO] {len(groups)}개 주제 · 뉴스 {total}건 수집")
        deliver(build_digest(groups))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
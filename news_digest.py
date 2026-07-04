#!/usr/bin/env python3
"""
korea-daily-news-digest
- Google News(한국) RSS로 뉴스 수집 → Claude API로 요약 → 텔레그램/파일로 전달
- 라즈베리 파이 cron으로 매일 실행하는 용도

필요 패키지:  pip install feedparser requests anthropic
환경변수(.env 또는 export):
  ANTHROPIC_API_KEY   (필수)
  TELEGRAM_BOT_TOKEN  (선택 - 있으면 텔레그램 전송)
  TELEGRAM_CHAT_ID    (선택)
  NEWS_KEYWORDS       (선택 - 쉼표구분. 비우면 주요뉴스 헤드라인)
                      예: "코스피,비트코인,인디게임"
"""

import os
import sys
import html
import datetime
import feedparser
import requests

# ---------- 설정 ----------
MODEL = "claude-haiku-4-5-20251001"   # 하루 1회라 하이쿠면 충분 (저렴)
MAX_ARTICLES = 20                     # 요약에 넘길 최대 기사 수
GNEWS_BASE = "https://news.google.com/rss"
LOCALE = "hl=ko&gl=KR&ceid=KR:ko"
OUT_DIR = os.path.expanduser("~/news_digest")  # 백업 저장 위치


# ---------- 1. 뉴스 수집 ----------
def fetch_news():
    keywords = [k.strip() for k in os.getenv("NEWS_KEYWORDS", "").split(",") if k.strip()]

    urls = []
    if keywords:
        for kw in keywords:
            urls.append(f"{GNEWS_BASE}/search?q={requests.utils.quote(kw)}&{LOCALE}")
    else:
        urls.append(f"{GNEWS_BASE}?{LOCALE}")  # 종합 헤드라인

    seen, articles = set(), []
    for url in urls:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = html.unescape(getattr(e, "title", "")).strip()
            if not title or title in seen:
                continue
            seen.add(title)
            src = ""
            if e.get("source"):
                src = e["source"].get("title", "")
            articles.append({
                "title": title,
                "link": getattr(e, "link", ""),
                "source": src,
                "published": getattr(e, "published", ""),
            })
    return articles[:MAX_ARTICLES]


# ---------- 2. Claude 요약 ----------
def summarize(articles):
    if not articles:
        return "오늘 수집된 뉴스가 없습니다."

    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today = datetime.date.today().isoformat()
    lines = [f"- {a['title']} ({a['source']})" for a in articles]
    prompt = (
        f"다음은 {today} 한국 뉴스 헤드라인 목록이야.\n\n"
        + "\n".join(lines)
        + "\n\n이걸 바탕으로 오늘의 뉴스 다이제스트를 만들어줘.\n"
          "- 주제별로 3~5개 묶음으로 그룹핑\n"
          "- 각 묶음마다 핵심을 1~2줄로 요약\n"
          "- 맨 위에 오늘의 한 줄 총평\n"
          "- 텔레그램에서 읽기 좋게 이모지 소제목, 간결하게\n"
          "- 없는 내용 지어내지 말고 제목에 있는 사실만 사용"
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


# ---------- 3. 전달 ----------
def deliver(text):
    today = datetime.date.today().isoformat()
    header = f"📰 오늘의 뉴스 다이제스트 ({today})\n\n"
    body = header + text

    # 항상 로컬 백업
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)

    # 텔레그램 (설정돼 있으면)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        # 텔레그램 4096자 제한 → 나눠 전송
        for chunk in [body[i:i + 3800] for i in range(0, len(body), 3800)]:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": chunk},
                timeout=30,
            )
            r.raise_for_status()
        print(f"[OK] 텔레그램 전송 완료 · 백업: {path}")
    else:
        print(f"[OK] 파일 저장: {path}  (텔레그램 미설정 → 전송 생략)")
        print("\n" + body)


# ---------- 메인 ----------
def main():
    try:
        articles = fetch_news()
        print(f"[INFO] 뉴스 {len(articles)}건 수집")
        digest = summarize(articles)
        deliver(digest)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

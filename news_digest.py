#!/usr/bin/env python3
"""
korea-daily-news-digest (분야별 · 무료 버전)
- 분야별로 Google News(한국) RSS 검색 → 신뢰 언론사 우선 정렬 → 텔레그램/파일 전달
- Claude API 미사용 = 과금 없음.
- 링크는 제목에 하이퍼링크로 걸어 메시지를 깔끔하게 유지.

필요 패키지:  pip install feedparser requests
환경변수(.env):
  TELEGRAM_BOT_TOKEN   (선택 - 있으면 텔레그램 전송)
  TELEGRAM_CHAT_ID     (선택)
  NEWS_CATEGORIES      (선택 - 쉼표구분. 비우면 아래 기본 7개 분야)
  MAX_PER_CATEGORY     (선택 - 분야당 기사 수, 기본 5)
  RECENCY_DAYS         (선택 - 최근 며칠 기사만, 기본 2 = 오늘~어제)
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

# 기본 분야 (분야명, 이모지) — 순서가 곧 출력 순서
DEFAULT_CATEGORIES = [
    ("정치", "🏛️"),
    ("경제", "💹"),
    ("사회", "🏙️"),
    ("문화", "🎨"),
    ("과학", "🔬"),
    ("스포츠", "⚽"),
    ("연예", "🎬"),
]

# 신뢰 언론사 (앞쪽일수록 우선)
TRUSTED = ["연합뉴스", "조선일보", "중앙일보", "동아일보",
           "KBS", "MBC", "SBS", "한겨레", "경향신문"]


def _rank(src):
    return TRUSTED.index(src) if src in TRUSTED else len(TRUSTED)


# ---------- 1. 분야별 수집 ----------
def fetch_news():
    max_per = int(os.getenv("MAX_PER_CATEGORY", "5"))
    recency = int(os.getenv("RECENCY_DAYS", "2"))

    env_cats = [c.strip() for c in os.getenv("NEWS_CATEGORIES", "").split(",") if c.strip()]
    categories = [(c, "📌") for c in env_cats] if env_cats else DEFAULT_CATEGORIES

    groups = OrderedDict()
    for name, emoji in categories:
        query = f"{name} when:{recency}d"
        url = f"{GNEWS_BASE}/search?q={requests.utils.quote(query)}&{LOCALE}"
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

        items.sort(key=lambda a: _rank(a["source"]))  # 신뢰 언론사 우선
        if items:
            groups[(name, emoji)] = items[:max_per]

    return groups


# ---------- 2. 렌더링 ----------
def render_html(groups):
    """텔레그램용: 제목에 링크 임베드 (URL 숨김)"""
    L = []
    for (name, emoji), items in groups.items():
        L.append(f"\n{emoji} <b>{name}</b>")
        for a in items:
            t = html.escape(a["title"])
            src = f" ({html.escape(a['source'])})" if a["source"] else ""
            if a["link"]:
                u = html.escape(a["link"], quote=True)
                L.append(f'  · <a href="{u}">{t}</a>{src}')
            else:
                L.append(f"  · {t}{src}")
    return L


def render_md(groups):
    """파일 백업용: 마크다운 링크"""
    L = []
    for (name, emoji), items in groups.items():
        L.append(f"\n{emoji} {name}")
        for a in items:
            src = f" ({a['source']})" if a["source"] else ""
            if a["link"]:
                L.append(f"  · [{a['title']}]({a['link']}){src}")
            else:
                L.append(f"  · {a['title']}{src}")
    return L


def _chunk_lines(lines, limit=3800):
    out, cur = [], ""
    for ln in lines:
        if cur and len(cur) + len(ln) + 1 > limit:
            out.append(cur)
            cur = ln
        else:
            cur = f"{cur}\n{ln}" if cur else ln
    if cur:
        out.append(cur)
    return out


# ---------- 3. 전달 ----------
def deliver(groups):
    today = datetime.date.today().isoformat()
    header = f"📰 오늘의 뉴스 ({today})"

    if not groups:
        body_md = header + "\n오늘 수집된 뉴스가 없습니다."
    else:
        body_md = header + "\n" + "\n".join(render_md(groups))

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body_md)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        html_lines = [header] + (render_html(groups) if groups else ["오늘 수집된 뉴스가 없습니다."])
        for chunk in _chunk_lines(html_lines):
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            if not r.ok:
                raise RuntimeError(f"Telegram {r.status_code}: {r.text}")
        print(f"[OK] 텔레그램 전송 완료 · 백업: {path}")
    else:
        print(f"[OK] 파일 저장: {path}  (텔레그램 미설정 → 전송 생략)")
        print("\n" + body_md)


def main():
    try:
        groups = fetch_news()
        total = sum(len(v) for v in groups.values())
        print(f"[INFO] {len(groups)}개 분야 · 뉴스 {total}건 수집")
        deliver(groups)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
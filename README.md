# korea-daily-news-digest

Google News(한국) RSS 수집 → Claude API 요약 → 텔레그램 전송(+로컬 백업).
라즈베리 파이 cron으로 매일 자동 실행.

## 설치

```bash
pip3 install -r requirements.txt
cp .env.example .env      # 값 채우기
chmod +x run.sh
```

## 테스트

```bash
./run.sh
```

## cron 등록 (매일 아침 8시)

`crontab -e` 에 추가:

```
0 8 * * * /home/pi/korea-daily-news-digest/run.sh >> /home/pi/korea-daily-news-digest/cron.log 2>&1
```

## 설정 (.env)

| 변수 | 필수 | 설명 |
|------|------|------|
| ANTHROPIC_API_KEY | O | Claude API 키 |
| TELEGRAM_BOT_TOKEN | X | 있으면 텔레그램 전송, 없으면 파일 저장만 |
| TELEGRAM_CHAT_ID | X | 텔레그램 대상 채팅 |
| NEWS_KEYWORDS | X | 쉼표구분. 비우면 종합 헤드라인 |

- 모델·기사수는 `news_digest.py` 상단 상수에서 조정.
- 요약 품질 ↑ : `MODEL`을 `claude-sonnet-5`로 변경.

## .gitignore

`.env` 는 커밋 금지 (키 노출). 아래 파일 참고.

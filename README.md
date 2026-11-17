# 데일리브리핑 자동화 (Threads + YouTube 나레이션)

## 1. 로컬 테스트
pip install -r requirements.txt   # + ffmpeg, 한글 폰트(Noto Sans CJK / 맑은 고딕) 필요
python main.py --sample --dry-run                 # 샘플 데이터 + 실제 TTS → 영상 생성
FAKE_TTS=1 python main.py --sample --dry-run      # TTS 없이 파이프라인만 점검
export ANTHROPIC_API_KEY=...
python main.py --dry-run                          # 실제 뉴스 수집·요약·영상 (게시/업로드 없음)

## 2. 실서비스 (GitHub Actions, 매일 07:00 KST)
리포지토리 Secrets 등록:
- ANTHROPIC_API_KEY
- THREADS_USER_ID, THREADS_ACCESS_TOKEN   (Meta 개발자 앱 → Threads API, threads_content_publish 권한)
- YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (Google Cloud → YouTube Data API v3, OAuth)
처음에는 YT_PRIVACY=private 로 두고 며칠 검수 후 public 전환.
Threads 토큰은 60일마다 갱신 필요.

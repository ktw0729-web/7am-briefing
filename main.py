"""매일 아침 실행: 뉴스 수집 → 요약 → 카드 → 나레이션 영상 → (Threads / YouTube)
사용:  python main.py --dry-run        # 게시·업로드 없이 영상까지만
       python main.py --sample         # API 없이 샘플 데이터로 테스트
"""
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from zoneinfo import ZoneInfo
import cards, tts, video

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--no-threads", action="store_true")
    ap.add_argument("--no-youtube", action="store_true")
    a = ap.parse_args()

    today = dt.datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = f"{today.year}.{today.month}.{today.day}"
    out = os.path.join("out", today.strftime("%Y-%m-%d")); os.makedirs(out, exist_ok=True)

    if a.sample:
        data = json.load(open("sample_data.json", encoding="utf-8"))
    else:
        from fetch_news import fetch
        from summarize import summarize
        data = summarize(fetch())
    json.dump(data, open(f"{out}/issues.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    issues = data["issues"]

    # 슬라이드: 인트로 + 이슈들 + 아웃트로
    slides = [("intro", data["intro"])]
    cards.title_card(f"{out}/s00.png", "", date_str, f"오늘의 핵심 이슈 {len(issues)}개")
    imgs = [f"{out}/s00.png"]
    for i, x in enumerate(issues, 1):
        cards.issue_card(f"{out}/s{i:02d}.png", i, len(issues), x, date_str)
        imgs.append(f"{out}/s{i:02d}.png")
        slides.append((f"issue{i}", f"{i}번. {x['title']}. {x['narration']}"))
    cards.title_card(f"{out}/s99.png", "", date_str, "시청해 주셔서 감사합니다")
    imgs.append(f"{out}/s99.png"); slides.append(("outro", data["outro"]))

    clips = []
    for k, ((name, text), img) in enumerate(zip(slides, imgs)):
        mp3, mp4 = f"{out}/{k:02d}.mp3", f"{out}/{k:02d}.mp4"
        tts.speak(text, mp3)
        video.clip(img, mp3, mp4)
        clips.append(os.path.abspath(mp4))
    final = f"{out}/news_{today.strftime('%Y%m%d')}.mp4"
    video.concat(clips, os.path.abspath(final), os.path.abspath(f"{out}/list.txt"))
    print("영상 생성:", final)
    if a.dry_run:
        return

    if not a.no_threads and os.getenv("THREADS_ACCESS_TOKEN"):
        from threads_post import post_thread
        print("Threads:", post_thread(date_str, data["intro"], issues))
    if not a.no_youtube and os.getenv("YT_REFRESH_TOKEN"):
        from youtube_upload import upload
        desc = f"{date_str} 7시 브리핑\n\n" + "\n".join(
            f"{i}. [{x['category']}] {x['title']} - {x['subtitle']}" for i, x in enumerate(issues, 1))
        desc += "\n\n※ 언론 보도를 AI로 요약·재구성한 영상입니다."
        print("YouTube:", upload(final, f"[{date_str}] 7시 브리핑 - 분야별 핵심 이슈 {len(issues)}", desc,
                                 os.getenv("YT_PRIVACY", "private")))

if __name__ == "__main__":
    main()

"""매일 아침 실행: 뉴스 수집 → 요약 → 자막+이미지 영상 → (Threads / YouTube)
사용:  python main.py --dry-run        # 게시·업로드 없이 영상까지만
       python main.py --sample         # 뉴스/Claude 없이 샘플 데이터로 테스트
"""
import argparse, datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from zoneinfo import ZoneInfo
import cards, cardnews, tts, video, images

def split_caption(text: str, limit: int = 70) -> list[str]:
    """나레이션을 자막 단위(문장, 길면 쉼표/공백에서 분할)로 쪼갠다."""
    out = []
    for sent in re.split(r"(?<=[.!?。])\s+", text.strip()):
        sent = sent.strip()
        while len(sent) > limit:
            cut = max(sent.rfind(", ", 0, limit), sent.rfind(" ", 0, limit))
            if cut < 15:
                cut = limit
            out.append(sent[:cut + 1].strip()); sent = sent[cut + 1:].strip()
        if sent:
            out.append(sent)
    merged = []                      # 너무 짧은 꼬리 조각(12자 미만)은 앞 문장에 붙인다
    for c in out:
        if merged and len(c) < 12 and len(merged[-1]) + len(c) < limit + 12:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return merged

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
    total = len(issues)

    # 슬라이드 정의: (종류, 음성 문장 목록, 화면 표시 문장 목록, 이슈, 번호, 사진목록)
    slides = [("intro", split_caption(data["intro"]), [], None, 0, [])]
    for i, x in enumerate(issues, 1):
        photos = images.fetch(x.get("image_keywords", []), f"{out}/photo{i:02d}")
        body = split_caption(x["narration"])
        slides.append(("issue", [f"{i}번. {x['title']}."] + body, body, x, i, photos))
    slides.append(("outro", split_caption(data["outro"]), [], None, 99, []))
    used_photo = any(s[5] for s in slides)
    cardnews.build(f"{out}/cardnews", date_str, issues, {s[4]: s[5] for s in slides if s[0] == "issue"},
                   images.provider() if used_photo else "")

    clips, n = [], 0
    for kind, spoken, shown, issue, idx, photos in slides:
        for ci, cap in enumerate(spoken):
            png, mp3, mp4 = f"{out}/f{n:03d}.png", f"{out}/a{n:03d}.mp3", f"{out}/c{n:03d}.mp4"
            if kind == "issue":
                photo = photos[ci % len(photos)] if photos else None
                # 기사 1건 = 1페이지: 본문 전체를 한 화면에 두고 읽는 문장만 강조 (ci=0은 번호/제목 낭독)
                cards.issue_frame(png, idx, total, issue, date_str, shown, ci - 1, photo,
                                  images.provider() if used_photo else "")
            else:
                sub = f"오늘의 핵심 이슈 {total}개" if kind == "intro" else "시청해 주셔서 감사합니다"
                cards.title_frame(png, date_str, sub, cap)
            tts.speak(cap, mp3)
            video.clip(png, mp3, mp4, pad=0.5 if ci == len(spoken) - 1 else 0.15)
            clips.append(os.path.abspath(mp4)); n += 1
    final = f"{out}/news_{today.strftime('%Y%m%d')}.mp4"
    video.concat(clips, os.path.abspath(final), os.path.abspath(f"{out}/list.txt"))
    print("영상 생성:", final, f"(자막 {n}컷)")
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
        if used_photo:
            desc += f"\n사진 출처: {images.provider()}"
        print("YouTube:", upload(final, f"[{date_str}] 7시 브리핑 - 분야별 핵심 이슈 {total}", desc,
                                 os.getenv("YT_PRIVACY", "private")))

if __name__ == "__main__":
    main()

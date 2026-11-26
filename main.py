"""매일 아침 실행: 뉴스 수집 → 요약 → 자막+이미지 영상 → (Threads / YouTube)
사용:  python main.py --dry-run        # 게시·업로드 없이 영상까지만
       python main.py --sample         # 뉴스/Claude 없이 샘플 데이터로 테스트
"""
import argparse, glob, datetime as dt, json, os, re, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from zoneinfo import ZoneInfo
import cards, cardnews, tts, video, images, brand, illust

# 자막 표시 방식: "sentence" = 읽는 문장 하나만 / "paragraph" = 읽는 단락 전체 (둘 다 흰색, 이전·다음 글은 숨김)
SUBTITLE_MODE = os.getenv("SUBTITLE_MODE", "sentence")

SLOTS = {"morning": 6 * 60, "noon": 11 * 60 + 30, "evening": 20 * 60 + 30}   # 게시 목표 시각(KST, 자정부터의 분)

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

def split_paragraphs(text: str, per: int = 2) -> list[str]:
    """나레이션을 단락 리스트로. 단락 구분이 없으면 문장 2개씩 묶는다."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text.strip()) if p.strip()]
    if len(paras) <= 1:
        sents = [x for x in re.split(r"(?<=[.!?。])\s+", text.strip()) if x]
        paras = [" ".join(sents[i:i + per]) for i in range(0, len(sents), per)] or [text.strip()]
    return paras

def publish_stage():
    """승인 후 단계: 유튜브 공개 전환 + Threads + 인스타그램 게시."""
    pend = json.load(open(os.getenv("PENDING", "pending/pending.json"), encoding="utf-8"))
    now = dt.datetime.now(ZoneInfo("Asia/Seoul"))
    key, day, slot = pend["key"], pend["day"], pend["slot"]
    flag = os.path.join("history", f"posted_{day}_{key}.flag")
    if pend["scheduled"]:
        if os.path.exists(flag):
            print("이미 게시된 판 -> 건너뜀"); return
        if slot < 60: slot *= 60   # 예전 pending(시 단위) 호환
        slot_dt = dt.datetime.fromisoformat(day).replace(hour=slot // 60, minute=slot % 60, tzinfo=ZoneInfo("Asia/Seoul"))
        late = (now - slot_dt).total_seconds() / 60
        if late > 150:
            print(f"승인이 목표 시각보다 {int(late)}분 늦음 -> 게시하지 않음(영상은 비공개 유지)"); return
        if late < 0:
            print(f"목표 시각 {slot_dt:%H:%M}까지 {int(-late*60)}초 대기"); time.sleep(-late * 60)
    brand.current["name"] = pend["edition_name"]
    video_id, link = pend["video_id"], ""
    if video_id and pend["public"]:
        from youtube_upload import make_public
        make_public(video_id); link = f"https://youtu.be/{video_id}"
        print("YouTube 공개 전환:", video_id)
    urls = pend["urls"]
    if os.getenv("THREADS_ACCESS_TOKEN"):
        from threads_post import post_thread
        print("Threads:", post_thread(pend["date_str"], pend["intro"], pend["issues"], link, urls, pend["page_url"]))
    if os.getenv("IG_ACCESS_TOKEN") and os.getenv("IG_USER_ID"):
        try:
            import instagram_post
            jp = [urls[k] for k in sorted(urls) if k.endswith(".jpg") and not k.startswith("99_")][:10]
            cap = instagram_post.build_caption(pend["date_str"], pend["edition_name"], pend["intro"], pend["issues"], pend["page_url"], link)
            print("Instagram:", instagram_post.post_carousel(jp, cap))
        except Exception as e:
            print("Instagram 게시 실패(무시):", e)
    os.makedirs("history", exist_ok=True)
    open(flag, "w").write(now.isoformat())
    try: os.remove(os.path.join("history", f"pending_{day}_{key}.json"))
    except OSError: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--no-threads", action="store_true")
    ap.add_argument("--no-youtube", action="store_true")
    ap.add_argument("--tts-sample", action="store_true", help="음성 후보 샘플 mp3 생성 후 종료")
    ap.add_argument("--no-site", action="store_true")
    ap.add_argument("--stage", choices=["all", "prepare", "publish"], default="all", help="prepare: 만들어 두기(비공개), publish: 승인 후 공개·게시")
    ap.add_argument("--no-illust", action="store_true")
    ap.add_argument("--illust-only", action="store_true", help="일러스트만 만들어 보고 종료(테스트)")
    a = ap.parse_args()

    if a.stage == "publish":
        return publish_stage()
    today = dt.datetime.now(ZoneInfo("Asia/Seoul"))
    # 하루 3판: 아침(06:00) / 점심(11:30) / 저녁(20:30) 게시. 실행 시각(KST)으로 판을 정한다. EDITION 환경변수로 강제 가능.
    key = os.getenv("EDITION") or ("morning" if today.hour < 8 else "noon" if today.hour < 16 else "evening")
    edition, edition_name = brand.EDITIONS[key]
    flag = os.path.join("history", f"posted_{today:%Y-%m-%d}_{key}.flag")
    pend_mark = os.path.join("history", f"pending_{today:%Y-%m-%d}_{key}.json")
    if os.getenv("DEDUP") == "1" and (os.path.exists(flag) or os.path.exists(pend_mark)):
        print(f"{today:%Y-%m-%d} {key}판은 이미 게시됨/승인 대기 중 -> 건너뜀"); return
    if os.getenv("DEDUP") == "1":   # 스케줄이 몇 시간 늦게 도착한 경우(GitHub 지연) 엉뚱한 시간대에 올리지 않고 건너뜀
        slot_ = SLOTS[key]
        late_min = today.hour * 60 + today.minute - slot_
        if late_min > 150 or late_min < -120:   # 너무 늦게/너무 일찍(전날 판의 지연 도착 등) 시작된 실행은 건너뜀
            print(f"{key}판 목표({slot_//60:02d}:{slot_%60:02d}) 대비 {late_min}분 차이로 시작됨 -> 게시하지 않고 건너뜀"); return
    brand.current["name"] = edition_name
    date_str = f"{today.year}.{today.month}.{today.day}"
    day = today.strftime("%Y-%m-%d")
    out = os.path.join("out", f"{day}_{key}"); os.makedirs(out, exist_ok=True)
    hist_path = os.path.join("history", f"{day}.json")
    covered = json.load(open(hist_path, encoding="utf-8")) if os.path.exists(hist_path) else []

    if a.tts_sample:
        txt = "안녕하세요, 굿모닝 브리핑입니다. 오늘 아침은 AI 대형 상장과 수출 1조 달러 돌파, APEC 외교전까지 핵심 이슈 열 가지를 전해드립니다."
        for v in ["ko-KR-InJoonNeural", "ko-KR-SunHiNeural"]:
            try:
                tts.speak(txt, f"{out}/voice_{v.split('-')[2].replace('Neural','')}.mp3", voice=v)
            except Exception as e:
                print("실패", v, e)
        import cardhost; print(cardhost.publish(out, 'tts_test', ["voice_*.mp3"])); return

    if a.sample:
        data = json.load(open("sample_data.json", encoding="utf-8"))
    else:
        from fetch_news import fetch
        from summarize import summarize
        data = summarize(fetch(), edition=edition, edition_name=edition_name, covered=covered)
    json.dump(data, open(f"{out}/issues.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not a.sample and not a.dry_run:   # 오늘 다룬 이슈 기록 -> 다음 판에서 중복 방지
        os.makedirs("history", exist_ok=True)
        json.dump(covered + [x["title"] for x in data["issues"]], open(hist_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    issues = data["issues"]
    total = len(issues)

    if a.illust_only:
        r = illust.make_all(issues, out, cards.COLORS); print(r)
        import cardhost; print(cardhost.publish(out, 'illust_test')); return
    ills = illust.make_all(issues, out, cards.COLORS) if os.getenv("ANTHROPIC_API_KEY") and not a.no_illust else {}

    # 슬라이드 정의: (종류, 음성 [(문장, 단락끝여부)], 화면 [(문장, 단락번호)], 이슈, 번호, 사진목록)
    slides = [("intro", [(" ".join(data["intro"].split()), False, -1)], [], None, 0, [])]
    for i, x in enumerate(issues, 1):
        photos = [ills[i]] if ills.get(i) else images.fetch(x.get("image_keywords", []), f"{out}/photo{i:02d}")
        spoken, shown = [(f"{i}번. {x['title']}.", True, -1)], []
        for pi, para in enumerate(split_paragraphs(x["narration"])):
            chunks = split_caption(para)
            for ci, c in enumerate(chunks):
                spoken.append((c, ci == len(chunks) - 1, pi)); shown.append((c, pi))
        slides.append(("issue", spoken, shown, x, i, photos))
    slides.append(("outro", [(" ".join(data["outro"].split()), False, -1)], [], None, 99, []))
    used_photo = any(p for s in slides for p in s[5] if "/ill" not in p)   # 사진 출처 표기는 스톡 사진을 쓴 경우만
    cardnews.build(f"{out}/cardnews", date_str, issues, {s[4]: s[5] for s in slides if s[0] == "issue"},
                   images.provider() if used_photo else "")

    clips, n = [], 0
    for kind, spoken, shown, issue, idx, photos in slides:
        for ci, (cap, para_end, pi) in enumerate(spoken):
            png, mp3, mp4 = f"{out}/f{n:03d}.png", f"{out}/a{n:03d}.mp3", f"{out}/c{n:03d}.mp4"
            if kind == "issue":
                # 단락이 바뀌면 화면(사진)이 바뀌고, 자막은 읽는 부분만 흰색으로 표시 (제목 낭독 중에는 자막 없음)
                photo = photos[max(pi, 0) % len(photos)] if photos else None
                if pi < 0:
                    units = []
                elif SUBTITLE_MODE == "paragraph":
                    units = [(c, 0) for c, p_ in shown if p_ == pi]
                else:
                    units = [(cap, 0)]
                cards.issue_frame(png, idx, total, issue, date_str, units, None, photo,
                                  images.provider() if used_photo else "")
            else:
                sub = f"오늘의 핵심 이슈 {total}개" if kind == "intro" else "시청해 주셔서 감사합니다"
                cards.title_frame(png, date_str, sub, cap)
            tts.speak(cap, mp3)
            video.clip(png, mp3, mp4, pad=0.5 if (ci == len(spoken) - 1 or (kind == 'issue' and para_end)) else 0.15)
            clips.append(os.path.abspath(mp4)); n += 1
    final = f"{out}/news_{today.strftime('%Y%m%d')}_{key}.mp4"
    video.concat(clips, os.path.abspath(final), os.path.abspath(f"{out}/list.txt"))
    print("영상 생성:", final, f"(자막 {n}컷)")
    if a.dry_run:
        return

    # 예약 게시: 스케줄 실행(PUBLISH_WAIT=1)은 목표 시각(06:00/11:30/20:30 KST) 전(최대 5시간)에 만들어 두고 그 시각에 맞춰 게시한다.
    slot = SLOTS[key]
    target = today.replace(hour=slot // 60, minute=slot % 60, second=0, microsecond=0)
    left = (target - dt.datetime.now(ZoneInfo("Asia/Seoul"))).total_seconds()
    scheduled = os.getenv("PUBLISH_WAIT") == "1" and 0 < left < 18000
    privacy = os.getenv("YT_PRIVACY", "private")
    prepare = a.stage == "prepare"   # 승인 방식: 영상은 비공개로만 올리고, 공개·Threads·인스타는 승인 후 publish 단계에서
    want_public = privacy == "public"
    if prepare:
        privacy = "private"; scheduled = False
    video_id = ""

    # 썸네일(유튜브)·링크 미리보기(웹페이지): 영상 첫 화면(제목 화면, 자막 없이) 1280x720
    from PIL import Image
    thumb = f"{out}/thumb.jpg"
    cards.title_frame(f"{out}/thumb_src.png", date_str, f"오늘의 핵심 이슈 {total}개", "")
    src = Image.open(f"{out}/thumb_src.png").convert("RGB")
    base = Image.new("RGB", src.size, "#101418"); base.paste(src, (0, 125))   # 글자를 화면 가운데로
    base.resize((1280, 720)).save(thumb, quality=92)

    if not a.no_youtube and os.getenv("YT_REFRESH_TOKEN"):
        from youtube_upload import upload
        desc = f"{brand.BRAND} · {edition_name} {date_str}\n\n" + "\n".join(
            f"{i}. [{x['category']}] {x['title']} - {x['subtitle']}" for i, x in enumerate(issues, 1))
        desc += "\n\n※ 언론 보도를 AI로 요약·재구성한 영상입니다."
        if used_photo:
            desc += f"\n사진 출처: {images.provider()}"
        # 공개 모드 + 예약 실행이면: 지금 올려 두고(처리 시간 확보) YouTube가 목표 시각에 자동 공개
        publish_at = target.isoformat() if (scheduled and privacy == "public") else None
        video_id = upload(final, f"[{date_str}] {edition_name} - 오늘의 핵심 이슈 {total}", desc, privacy, publish_at, thumb)
        print("YouTube:", video_id, f"(예약 공개 {publish_at})" if publish_at else f"({privacy})")

    # 상세 웹페이지(GitHub Pages): 스레드 링크로 연결. 목표 시각 전에 미리 올려 둔다.
    page_url = ""
    if not a.no_site:
        import sitepage
        vurl = f"https://youtu.be/{video_id}" if (video_id and privacy == "public") else ""
        page_url = sitepage.publish(out, f"{day}_{key}" + ("_test" if a.sample else ""), date_str, edition_name, data["intro"], issues,
                                    {s_[4]: s_[5] for s_ in slides if s_[0] == "issue"}, cards.COLORS, vurl,
                                    f"사진 출처: {images.provider()}" if used_photo else "", thumb)
        print("웹페이지:", page_url or "(없음)")

    if scheduled:
        left = (target - dt.datetime.now(ZoneInfo("Asia/Seoul"))).total_seconds()
        if left > 0:
            print(f"목표 시각 {target:%H:%M}까지 {int(left)}초 대기")
            time.sleep(left)

    if not a.no_threads and os.getenv("THREADS_ACCESS_TOKEN"):
        from threads_post import post_thread
        link = f"https://youtu.be/{video_id}" if (video_id and privacy == "public") else ""
        import cardhost
        cdir = f"{out}/cardnews"
        if os.getenv("IG_ACCESS_TOKEN"):   # 인스타는 JPEG만 허용 → 같은 카드의 jpg 사본을 함께 올림
            from PIL import Image
            for f_ in sorted(glob.glob(f"{cdir}/*.png")):
                Image.open(f_).convert("RGB").save(f_[:-4] + ".jpg", quality=92)
        urls = cardhost.publish(cdir, f"{today.strftime('%Y%m%d')}_{key}", ["ill*.png", "[0-9]*.png", "*_cover.png", "*.jpg"])
        print("카드 이미지 URL:", len(urls), "개")
        if prepare:
            pend = {"day": day, "key": key, "slot": slot, "scheduled": os.getenv("DEDUP") == "1", "public": want_public,
                    "video_id": video_id, "urls": urls, "date_str": date_str, "edition_name": edition_name,
                    "intro": data["intro"], "issues": issues, "page_url": page_url}
            os.makedirs("pending", exist_ok=True); os.makedirs("history", exist_ok=True)
            for pp in (("pending/pending.json",) if a.sample else ("pending/pending.json", pend_mark)):   # 샘플 테스트는 정기 실행을 막는 표시 파일을 남기지 않음
                json.dump(pend, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
            print("승인 대기 상태로 저장:", pend_mark); return
        print("Threads:", post_thread(date_str, data["intro"], issues, link, urls, page_url))
        if os.getenv("IG_ACCESS_TOKEN") and os.getenv("IG_USER_ID"):
            try:
                import instagram_post
                jp = [urls[k] for k in sorted(urls) if k.endswith(".jpg") and not k.startswith("99_")][:10]   # 표지+이슈 9개(안내 카드·10번째 이슈는 캡션으로 대체)
                cap = instagram_post.build_caption(date_str, brand.current["name"], data["intro"], issues, page_url, link)
                print("Instagram:", instagram_post.post_carousel(jp, cap))
            except Exception as e:
                print("Instagram 게시 실패(무시):", e)
        os.makedirs("history", exist_ok=True); open(flag, "w").write(dt.datetime.now(ZoneInfo("Asia/Seoul")).isoformat())

if __name__ == "__main__":
    main()

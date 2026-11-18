"""Threads API 게시: 첫 글(헤드라인 목록) + 답글(이슈별 요약)."""
import os, time, requests
import brand

API = "https://graph.threads.net/v1.0"

def _publish(text, reply_to=None, image_url=None):
    uid, tok = "me", os.environ["THREADS_ACCESS_TOKEN"]  # 토큰 주인 계정으로 게시(사용자 ID 불필요)
    data = {"media_type": "IMAGE" if image_url else "TEXT", "text": text[:500], "access_token": tok}
    if image_url:
        data["image_url"] = image_url
    if reply_to:
        data["reply_to_id"] = reply_to
    c = requests.post(f"{API}/{uid}/threads", data=data, timeout=30)
    cj = c.json()
    if "id" not in cj:
        raise RuntimeError(f"Threads 컨테이너 생성 실패 {c.status_code}: {cj}")
    time.sleep(8 if image_url else 3)
    for attempt in range(4):   # 이미지는 처리 중이면 실패할 수 있어 재시도
        r = requests.post(f"{API}/{uid}/threads_publish", data={"creation_id": cj["id"], "access_token": tok}, timeout=30)
        if r.ok:
            return r.json()["id"]
        time.sleep(6)
    raise RuntimeError(f"Threads 게시 실패 {r.status_code}: {r.text}")

def _publish_safe(text, reply_to, image_url):
    """이미지 게시가 실패하면 텍스트만으로 게시해 스레드가 끊기지 않게 한다."""
    if image_url:
        try:
            return _publish(text, reply_to, image_url)
        except Exception as e:
            print("이미지 게시 실패, 텍스트로 대체:", e)
    return _publish(text, reply_to)

def post_thread(date_str, intro, issues, link="", images=None):
    images = images or {}
    head = f"📰 {date_str} {brand.current['name']}\n{intro}\n" + (f"▶ 영상: {link}\n" if link else "") + "\n" + "\n".join(
        f"{i}. [{x['category']}] {x['title']}" for i, x in enumerate(issues, 1))
    root = _publish_safe(head, None, images.get("00_cover.png"))
    prev = root
    for i, x in enumerate(issues, 1):
        body = f"{i}. [{x['category']}] {x['title']}\n{x['summary']}\n(참고: {', '.join(x.get('sources', []))})"
        prev = _publish_safe(body, prev, images.get(f"{i:02d}.png"))
        time.sleep(2)
    return root

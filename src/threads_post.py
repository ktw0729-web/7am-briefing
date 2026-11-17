"""Threads API 게시: 첫 글(헤드라인 목록) + 답글(이슈별 요약)."""
import os, time, requests
import brand

API = "https://graph.threads.net/v1.0"

def _publish(text, reply_to=None):
    uid, tok = "me", os.environ["THREADS_ACCESS_TOKEN"]  # 토큰 주인 계정으로 게시(사용자 ID 불필요)
    data = {"media_type": "TEXT", "text": text[:500], "access_token": tok}
    if reply_to:
        data["reply_to_id"] = reply_to
    c = requests.post(f"{API}/{uid}/threads", data=data, timeout=30)
    cj = c.json()
    if "id" not in cj:
        raise RuntimeError(f"Threads 컨테이너 생성 실패 {c.status_code}: {cj}")
    time.sleep(3)
    r = requests.post(f"{API}/{uid}/threads_publish", data={"creation_id": cj["id"], "access_token": tok}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Threads 게시 실패 {r.status_code}: {r.text}")
    return r.json()["id"]

def post_thread(date_str, intro, issues, link=""):
    head = f"📰 {date_str} {brand.current['name']}\n{intro}\n" + (f"▶ 영상: {link}\n" if link else "") + "\n" + "\n".join(
        f"{i}. [{x['category']}] {x['title']}" for i, x in enumerate(issues, 1))
    root = _publish(head)
    prev = root
    for i, x in enumerate(issues, 1):
        body = f"{i}. [{x['category']}] {x['title']}\n{x['summary']}\n(참고: {', '.join(x.get('sources', []))})"
        prev = _publish(body, reply_to=prev)
        time.sleep(2)
    return root

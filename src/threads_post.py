"""Threads API 게시: 첫 글(헤드라인 목록) + 답글(이슈별 요약)."""
import os, time, requests
import brand

API = "https://graph.threads.net/v1.0"

def _publish(text, reply_to=None):
    uid, tok = os.environ["THREADS_USER_ID"], os.environ["THREADS_ACCESS_TOKEN"]
    data = {"media_type": "TEXT", "text": text[:500], "access_token": tok}
    if reply_to:
        data["reply_to_id"] = reply_to
    cid = requests.post(f"{API}/{uid}/threads", data=data, timeout=30).json()["id"]
    time.sleep(3)
    r = requests.post(f"{API}/{uid}/threads_publish", data={"creation_id": cid, "access_token": tok}, timeout=30)
    r.raise_for_status()
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

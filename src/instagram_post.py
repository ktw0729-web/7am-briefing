"""Instagram 캐러셀 게시(같은 카드 이미지). 실패해도 파이프라인은 계속되도록 호출 쪽에서 try/except."""
import os, time, requests

API = "https://graph.facebook.com/v21.0"

def _tok():
    return "".join(os.environ["IG_ACCESS_TOKEN"].split()).strip("\"'")

def _post(path, **data):
    data["access_token"] = _tok()
    r = requests.post(f"{API}/{path}", data=data, timeout=30)
    j = r.json()
    if "id" not in j:
        raise RuntimeError(f"Instagram {path} 실패 {r.status_code}: {j}")
    return j["id"]

def _wait(cid, tries=20):
    for _ in range(tries):
        r = requests.get(f"{API}/{cid}", params={"fields": "status_code", "access_token": _tok()}, timeout=30).json()
        if r.get("status_code") == "FINISHED":
            return
        if r.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram 미디어 처리 실패: {r}")
        time.sleep(3)
    raise RuntimeError("Instagram 미디어 처리 시간 초과")

def build_caption(date_str, name, intro, issues, page_url="", link=""):
    cap = f"📰 {date_str} {name}\n{intro}\n\n"
    for i, x in enumerate(issues, 1):
        cap += f"{i}. [{x['category']}] {x['title']}\n"
    if page_url: cap += f"\n📖 전체 내용: {page_url}"
    if link: cap += f"\n▶ 영상: {link}"
    return cap[:2200]

def post_carousel(image_urls, caption):
    """image_urls: 공개 JPEG URL 리스트(최대 10장). 게시된 미디어 ID 반환."""
    uid = os.environ["IG_USER_ID"]
    urls = image_urls[:10]
    if len(urls) < 2:
        raise RuntimeError("캐러셀은 이미지 2장 이상 필요")
    kids = []
    for u in urls:
        c = _post(f"{uid}/media", image_url=u, is_carousel_item="true")
        kids.append(c)
    for c in kids:
        _wait(c)
    car = _post(f"{uid}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)
    _wait(car)
    return _post(f"{uid}/media_publish", creation_id=car)

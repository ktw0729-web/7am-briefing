"""이슈별 이미지 확보. Pixabay(우선) 또는 Pexels 무료 API 사용.
키가 없거나 실패하면 빈 리스트 -> 카드가 분야 색상 일러스트로 대체."""
import os, requests

def provider() -> str:
    if os.getenv("PIXABAY_API_KEY"):
        return "Pixabay"
    if os.getenv("PEXELS_API_KEY"):
        return "Pexels"
    return ""

# 내용과 무관한 국기·외국 랜드마크 사진이 걸리는 것을 막기 위한 태그 필터 (Pixabay는 hit마다 tags 제공)
_BAD_TAGS = ("flag", "flags", "banner", "germany", "german", "deutschland", "reichstag", "bundestag",
             "usa", "american flag", "eu flag", "european union", "union jack", "united kingdom")

def _bad(tags: str, kw: str) -> bool:
    words = set(w.strip() for w in tags.lower().replace(",", " ").split())
    k = set(kw.lower().split())
    return any(b in words and b not in k for b in _BAD_TAGS if " " not in b)

def _search(kw: str) -> list[str]:
    if os.getenv("PIXABAY_API_KEY"):
        r = requests.get("https://pixabay.com/api/", params={
            "key": os.environ["PIXABAY_API_KEY"], "q": kw, "image_type": "photo",
            "orientation": "horizontal", "safesearch": "true", "per_page": 20}, timeout=20)
        r.raise_for_status()
        # 기본 정렬(관련도순) 사용 + 국기 등 엉뚱한 태그 제외
        hits = [h for h in r.json().get("hits", []) if not _bad(h.get("tags", ""), kw)]
        return [h["largeImageURL"] for h in hits[:2]]
    r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": os.environ["PEXELS_API_KEY"]},
                     params={"query": kw, "per_page": 2, "orientation": "landscape"}, timeout=20)
    r.raise_for_status()
    return [p["src"]["large"] for p in r.json().get("photos", [])]

def fetch(keywords: list[str], dest_prefix: str, n: int = 3) -> list[str]:
    if not provider() or not keywords:
        return []
    paths = []
    try:
        for kw in keywords:
            for url in _search(kw):
                if len(paths) >= n:
                    break
                img = requests.get(url, timeout=30)
                img.raise_for_status()
                path = f"{dest_prefix}_{len(paths)}.jpg"
                open(path, "wb").write(img.content)
                paths.append(path)
            if len(paths) >= n:
                break
    except Exception as e:
        print("이미지 가져오기 실패(무시):", e)
    return paths

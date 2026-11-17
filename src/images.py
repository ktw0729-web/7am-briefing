"""이슈별 이미지 확보: Pexels(무료 라이선스) 검색. 키가 없거나 실패하면 빈 리스트 -> 카드가 자체 일러스트로 대체."""
import os, requests

def fetch(keywords: list[str], dest_prefix: str, n: int = 3) -> list[str]:
    key = os.getenv("PEXELS_API_KEY")
    if not key or not keywords:
        return []
    paths = []
    try:
        for kw in keywords:
            r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                             params={"query": kw, "per_page": 2, "orientation": "landscape"}, timeout=20)
            r.raise_for_status()
            for p in r.json().get("photos", []):
                if len(paths) >= n:
                    break
                img = requests.get(p["src"]["large"], timeout=30)
                img.raise_for_status()
                path = f"{dest_prefix}_{len(paths)}.jpg"
                open(path, "wb").write(img.content)
                paths.append(path)
            if len(paths) >= n:
                break
    except Exception as e:
        print("이미지 가져오기 실패(무시):", e)
    return paths

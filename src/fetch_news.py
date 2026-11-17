"""분야별 뉴스 헤드라인 수집 (Google News RSS, 한국어)."""
import feedparser

BASE = "https://news.google.com/rss"
FEEDS = {
    "경제": f"{BASE}/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",
    "국제": f"{BASE}/headlines/section/topic/WORLD?hl=ko&gl=KR&ceid=KR:ko",
    "기술": f"{BASE}/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko",
    "사회": f"{BASE}/headlines/section/topic/NATION?hl=ko&gl=KR&ceid=KR:ko",
    "산업": f"{BASE}/search?q=산업+when:1d&hl=ko&gl=KR&ceid=KR:ko",
}

def fetch(per_category: int = 15) -> dict[str, list[dict]]:
    out = {}
    for cat, url in FEEDS.items():
        feed = feedparser.parse(url)
        out[cat] = [
            {"title": e.title, "source": getattr(e, "source", {}).get("title", ""), "link": e.link}
            for e in feed.entries[:per_category]
        ]
    return out

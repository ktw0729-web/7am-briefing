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

EXCLUDE = ["조선일보", "Chosun"]

def fetch(per_category: int = 30) -> dict[str, list[dict]]:
    out = {}
    for cat, url in FEEDS.items():
        feed = feedparser.parse(url)
        items = [
            {"title": e.title, "source": getattr(e, "source", {}).get("title", ""), "link": e.link}
            for e in feed.entries
        ]
        # 제외 언론사(사용자 요청): 출처 또는 제목 끝의 " - 언론사"에 해당 이름이 있으면 뺀다
        items = [it for it in items if not any(b in it["source"] or b in it["title"].rsplit(" - ", 1)[-1] for b in EXCLUDE)]
        out[cat] = items[:per_category]
    return out

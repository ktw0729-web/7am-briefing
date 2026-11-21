"""분야별 이슈 10개 선정 + 요약 + 나레이션 대본 생성. GEMINI_API_KEY가 있으면 Gemini(무료 티어), 없으면 Claude 사용."""
import json, os, time, requests

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PROMPT = """아래는 지금 시점의 분야별 뉴스 헤드라인(언론사 포함)이다.
이번 판은 [{edition}판]이다. 같은 사건을 다룬 기사는 하나로 묶어, 분야가 고르게 섞이도록 오늘의 핵심 이슈 {n}개를 골라라.

규칙:
- 오늘 앞선 판에서 이미 다룬 이슈 목록: {covered}
  같은 이슈는 새로운 진전이 있을 때만 다시 고르고(그 경우 제목에 새 진전을 드러낼 것), 그렇지 않으면 다른 이슈를 고를 것.
- 헤드라인에 없는 사실·수치를 지어내지 말 것. 불확실하면 쓰지 말 것.
- 기사 문장을 그대로 베끼지 말고 직접 재작성할 것.
- 각 이슈: category(경제/산업/국제/기술/사회), title(20자 내외), subtitle(핵심 쟁점 한 줄, 40자 내외),
  summary(스레드용 2~3문장, 200자 이내), narration(음성용 구어체, 숫자는 읽는 방식으로. 2~3개 단락으로 나누고 단락 사이는 빈 줄(\\n\\n)로 구분. 단락마다 하나의 포인트: 무슨 일/왜 중요한가/앞으로 볼 점. 전체 4~6문장),
  sources(참고한 언론사 이름 목록),
  image_keywords(이슈를 상징하는 일반적인 사진 검색어 영어 2개, 예: ["stock market", "city skyline"]. 실존 인물·브랜드·로고 금지)
- 추가로 intro(오프닝 멘트 1~2문장(“안녕하세요, {edition_name}입니다”로 시작))와 outro(마무리 1문장) 작성.
- 오직 JSON만 출력: {{"intro": "", "outro": "", "issues": [ ... ]}}

헤드라인:
{headlines}
"""

def _gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 16000}}
    last = None
    for i in range(4):
        r = requests.post(url, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, json=body, timeout=180)
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"{r.status_code} {r.text[:200]}"; time.sleep(15 * (i + 1)); continue
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    raise RuntimeError(f"Gemini 호출 실패: {last}")

def _claude(prompt: str) -> str:
    import anthropic
    msg = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=16000, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text")

def summarize(news: dict, n: int = 10, edition: str = "아침", edition_name: str = "브리핑", covered=()) -> dict:
    lines = []
    for cat, items in news.items():
        for it in items:
            lines.append(f"[{cat}] {it['title']}")
    prompt = PROMPT.format(n=n, edition=edition, edition_name=edition_name, covered=("; ".join(covered) or "없음"), headlines="\n".join(lines))
    text = (_gemini(prompt) if os.getenv("GEMINI_API_KEY") else _claude(prompt)).strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    return json.loads(text)

"""Claude로 분야별 이슈 10개 선정 + 요약 + 나레이션 대본 생성."""
import json, os, anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

PROMPT = """아래는 오늘 아침 분야별 뉴스 헤드라인(언론사 포함)이다.
같은 사건을 다룬 기사는 하나로 묶어, 분야가 고르게 섞이도록 오늘의 핵심 이슈 {n}개를 골라라.

규칙:
- 헤드라인에 없는 사실·수치를 지어내지 말 것. 불확실하면 쓰지 말 것.
- 기사 문장을 그대로 베끼지 말고 직접 재작성할 것.
- 각 이슈: category(경제/산업/국제/기술/사회), title(20자 내외), subtitle(핵심 쟁점 한 줄, 40자 내외),
  summary(스레드용 2~3문장, 200자 이내), narration(음성용 3~4문장, 구어체, 숫자는 읽는 방식으로),
  sources(참고한 언론사 이름 목록)
- 추가로 intro(오프닝 멘트 1~2문장(“안녕하세요, 7시 브리핑입니다”로 시작))와 outro(마무리 1문장) 작성.
- 오직 JSON만 출력: {{"intro": "", "outro": "", "issues": [ ... ]}}

헤드라인:
{headlines}
"""

def summarize(news: dict, n: int = 10) -> dict:
    lines = []
    for cat, items in news.items():
        for it in items:
            lines.append(f"[{cat}] {it['title']}")
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=6000,
        messages=[{"role": "user", "content": PROMPT.format(n=n, headlines="\n".join(lines))}],
    )
    text = msg.content[0].text.strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    return json.loads(text)

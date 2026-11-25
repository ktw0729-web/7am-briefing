"""분야별 이슈 10개 선정 + 요약 + 나레이션 대본 생성. GEMINI_API_KEY가 있으면 Gemini(무료 티어), 없으면 Claude 사용."""
import json, os, re, time, requests
from datetime import datetime
from zoneinfo import ZoneInfo

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

PROMPT = """아래는 지금 시점의 분야별 뉴스 헤드라인(언론사 포함)이다.
오늘 날짜는 {today_kr}(한국시간)이다. 날짜를 언급해야 한다면 반드시 이 날짜만 쓰고, 헤드라인 속 다른 날짜나 추측한 날짜는 쓰지 말 것.
이번 판은 [{edition}판]이다. 같은 사건을 다룬 기사는 하나로 묶어, 오늘의 핵심 이슈 {n}개를 골라라.
선정 기준(중요도 순): ① 여러 언론사가 동시에 다루는 사건(헤드라인에 같은 사건이 몇 번 나오는지 세어 많을수록 중요) ② 국민 생활·경제·안보에 미치는 영향 범위 ③ 새로운 진전·발표가 있는 사건 ④ 단순 연예·스포츠·가십·홍보성 기사는 제외.
분야는 억지로 균등하게 맞추지 말고 중요도를 우선하되, 한 분야가 {n}개 중 4개를 넘지 않게 하고 가능하면 3개 이상의 분야를 포함할 것.

규칙:
- 오늘 앞선 판에서 이미 다룬 이슈 목록: {covered}
  같은 이슈는 새로운 진전이 있을 때만 다시 고르고(그 경우 제목에 새 진전을 드러낼 것), 그렇지 않으면 다른 이슈를 고를 것.
- 표기 규칙(title·subtitle·summary·narration 모두): 숫자는 한글로 풀어 쓰지 말고 아라비아 숫자로(예: 1.5배, 10조 달러, 2030조, 65세, 16개국), 영어는 한글 음역 대신 원래 영문으로(예: AI, APEC, USTR, SK, S&P500, MS) 쓸 것.
- 헤드라인에 없는 사실·수치를 지어내지 말 것. 불확실하면 쓰지 말 것.
- 기사 문장을 그대로 베끼지 말고 직접 재작성할 것.
- 각 이슈: category(경제/산업/국제/기술/사회), title(20자 내외), subtitle(핵심 쟁점 한 줄, 40자 내외),
  summary(스레드용 2~3문장, 200자 이내), narration(음성용 구어체. 2~3개 단락으로 나누고 단락 사이는 빈 줄(\\n\\n)로 구분. 단락마다 하나의 포인트: 무슨 일/왜 중요한가/앞으로 볼 점. 전체 4~6문장),
  sources(참고한 언론사 이름 목록),
  image_keywords(이슈를 상징하는 일반적인 사진 검색어 영어 2개, 예: ["stock market", "city skyline"]. 실존 인물·브랜드·로고 금지)
- 추가로 intro(오프닝 멘트 1~2문장(“안녕하세요, {edition_name}입니다”로 시작))와 outro(마무리 1문장) 작성.
- 오직 JSON만 출력: {{"intro": "", "outro": "", "issues": [ ... ]}}

헤드라인:
{headlines}
"""

def _models(key: str) -> list:
    """사용 가능한 flash 모델 목록(안정판 우선, 최신 우선). GEMINI_MODEL을 직접 지정하면 맨 앞에 둔다."""
    import re
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key}, timeout=60)
    r.raise_for_status()
    cands = []
    for m in r.json().get("models", []):
        n = m["name"].split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []): continue
        if not n.startswith("gemini-") or "flash" not in n: continue
        if any(x in n for x in ("lite", "image", "tts", "live", "audio", "thinking", "exp", "latest", "omni")): continue
        v = tuple(int(x) for x in re.findall(r"\d+", n.split("flash")[0])) or (0,)
        cands.append((("preview" not in n), v, n))
    names = [c[2] for c in sorted(cands, reverse=True)]
    if os.getenv("GEMINI_MODEL"):
        names.insert(0, os.environ["GEMINI_MODEL"])
    print("Gemini 후보(시도 순서):", names)
    return names

def _gemini_once(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 16000}}
    last = None
    for model in _models(key):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=180)
            except requests.RequestException as e:
                last = f"{model}: {e}"; time.sleep(10); continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"{model}: {r.status_code} {r.text[:150]}"; time.sleep(10 * (attempt + 1)); continue
            if r.status_code != 200:
                last = f"{model}: {r.status_code} {r.text[:150]}"; break   # 404/400 등 -> 다른 모델로
            try:
                parts = r.json()["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts)
                if "{" in text:
                    print("Gemini 사용 모델:", model); return text
                last = f"{model}: 빈 응답"
            except Exception as e:
                last = f"{model}: 응답 해석 실패 {e}"
            break
        print("Gemini 실패, 다른 모델 시도:", last)
    raise RuntimeError(f"Gemini 호출 실패: {last}")

def _gemini(prompt: str) -> str:
    """전 모델이 과부하(503)일 수 있어, 전체 후보 순회를 최대 5회 반복한다(회차 사이 90초 대기)."""
    err = None
    for rnd in range(5):
        try:
            return _gemini_once(prompt)
        except RuntimeError as e:
            err = e
            if rnd < 4:
                print(f"Gemini 전체 후보 실패({rnd+1}/5회차) -> 90초 후 재시도"); time.sleep(90)
    raise err

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
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    today_kr = f"{now.year}년 {now.month}월 {now.day}일"
    prompt = PROMPT.format(today_kr=today_kr, n=n, edition=edition, edition_name=edition_name, covered=("; ".join(covered) or "없음"), headlines="\n".join(lines))
    text = (_gemini(prompt) if os.getenv("GEMINI_API_KEY") else _claude(prompt)).strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    data = json.loads(text)
    return _fix_dates(data, now)

def _fix_dates(data, now):
    """생성 글에 오늘이 아닌 'N월 M일'이 들어가면 오늘 날짜로 바로잡는다."""
    pat = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")
    def fix(t):
        if not isinstance(t, str): return t
        return pat.sub(lambda m: m.group(0) if (int(m.group(1)), int(m.group(2))) == (now.month, now.day) else f"{now.month}월 {now.day}일", t)
    for k in ("intro", "outro"):
        if k in data: data[k] = fix(data[k])
    return data

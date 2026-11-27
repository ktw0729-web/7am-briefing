"""아침 브리핑용 자료를 Gemini(Google 검색 grounding)로 수집해 data/briefing_data.md 로 저장.
브리핑 에이전트(Claude)가 이 파일을 읽어 사용한다. 필요: GEMINI_API_KEY."""
import os, sys, time, requests
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from summarize import _models

now = datetime.now(ZoneInfo("Asia/Seoul"))
today = f"{now.year}년 {now.month}월 {now.day}일({'월화수목금토일'[now.weekday()]}) {now:%H:%M} KST"

PROMPT = f"""지금은 {today}이다. Google 검색으로 실제 최신 자료를 확인해 한국어 마크다운으로 작성하라.
공통 규칙: 확인하지 못한 수치·사실은 '확인 못 함'으로 쓰고 절대 추측하지 말 것. 각 항목마다 출처 매체명과 기사 게재일, 원문 URL을 붙일 것. 출처 간 값이 다르면 병기. 검색 결과 제목만 보고 쓰지 말 것.

# 1. 대전광역시 오늘 날씨 (공주 아님, 기상청 발표 기반)
최저·최고기온, 하늘, 강수확률·예상강수량(대전 단독 수치 없으면 그렇게 표시), 풍속·체감온도, 미세먼지.
# 2. 국내외 주요 뉴스 5건 (정치·경제·사회·국제, 공공조달·전자정부, AI·모바일·자율주행)
제목·발표일 / 핵심 1~2문장 / 영향 / URL
# 3. IT·정보통신 주요 뉴스 3건 (AI·반도체·클라우드·사이버보안·개인정보·공공 정보화), 홍보성 제외
# 4. 국내 증시: 전일 코스피·코스닥 종가·등락률, 외국인·기관·개인 수급(출처별 차이), 주요 업종·종목, 오늘 일정·이슈
# 5. 미국 증시: 가장 최근 마감한 정규장(날짜 명시) S&P500·나스닥·다우·필라델피아반도체 종가·등락률, 주요 종목, 미 10년물 금리·달러·유가, 연준 관련, 최근 1~4주 맥락
# 6. 조달청 본청 최신 입찰공고·제안요청(IT·정보보안·디지털서비스 우선)·계약(단, 물품 입찰공고·물품계약은 제외하고 용역·공사만): 사업명·공고번호·금액·마감·참가자격. 집계 사이트 기반이면 '제3자 집계, 나라장터 원문 확인 필요' 표시.
"""

def call(model, key):
    body = {"contents": [{"parts": [{"text": PROMPT}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"maxOutputTokens": 16000, "temperature": 0.2}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for a in range(3):
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=240)
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  {model} 시도{a+1}: HTTP {r.status_code} {r.text[:300]}", flush=True)
            time.sleep(15 * (a + 1)); continue
        r.raise_for_status()
        c = r.json()["candidates"][0]
        text = "".join(p.get("text", "") for p in c["content"]["parts"])
        srcs = [w.get("web", {}) for w in c.get("groundingMetadata", {}).get("groundingChunks", [])]
        return text, srcs
    raise RuntimeError(f"{model} 재시도 실패")

def main():
    key = os.environ["GEMINI_API_KEY"]
    err = None
    for model in _models(key):
        try:
            text, srcs = call(model, key)
            if len(text) < 200: raise RuntimeError("빈 응답")
            out = [f"# Gemini 수집 자료 — 생성 {today} (모델 {model})",
                   "> Gemini+Google 검색 결과이며 검증 전 자료입니다. 브리핑 시 핵심 수치는 원문 확인 필요.\n", text,
                   "\n## 검색 근거(grounding) 출처"]
            out += [f"- [{s.get('title','')}]({s.get('uri','')})" for s in srcs if s.get("uri")]
            os.makedirs("data", exist_ok=True)
            open("data/briefing_data.md", "w", encoding="utf-8").write("\n".join(out))
            print("저장 완료:", model, len(text)); return
        except Exception as e:
            err = e; print("실패, 다음 모델:", model, e)
    raise SystemExit(f"Gemini 수집 실패: {err}")

main()

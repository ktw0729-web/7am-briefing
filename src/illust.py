"""이슈마다 기사와 어울리는 벡터(SVG) 일러스트를 Claude로 그려 PNG로 변환한다. 실패하면 빈 값을 돌려줘 기존 사진/색상 그림으로 대체된다."""
import os, re, json, concurrent.futures as cf
import anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
W, H = 1200, 700

PROMPT = """뉴스 카드용 일러스트를 SVG 코드로 그려라.

주제: [{category}] {title} — {subtitle}
요약: {summary}

스타일(모든 일러스트를 같은 느낌으로):
- 따뜻한 크림색 배경(#FBF3E4~#F6E7CC 그라데이션)에 부드러운 파스텔 톤, 플랫/아이소메트릭 디오라마 느낌. 포인트 색은 {color} 계열.
- 주제를 상징하는 사물·장면 2~4개를 '떠 있는 섬(둥근 받침)'이나 작은 무대 위에 배치하고, 점선·길·화살표로 관계를 연결한다.
- 은은한 그림자와 겹침으로 깊이를 주되 단순하고 깔끔하게. 둥근 모서리, 두꺼운 외곽선 없음.
- 기사의 핵심 개념이 한눈에 보이게(예: 금리=저울·동전, 반도체=칩, 재난=구조 헬멧·배, 정상회담=두 깃발 사이 악수 대신 마주 선 건물).

엄격한 규칙:
- <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" ...> 로 시작해 </svg>로 끝낸다. 설명 없이 SVG 코드만 출력.
- 글자(<text>), 숫자, 로고, 국기, 실존 인물의 얼굴·초상, 브랜드 상징은 절대 넣지 않는다.
- 외부 링크·<image>·<script>·<foreignObject>·폰트 사용 금지. 도형(path, rect, circle, ellipse, polygon, g, linearGradient, radialGradient, filter 제외)만 사용.
- 코드는 간결하게(도형 40개 이하, 6000자 이내).
- 핵심 요소는 가운데 70% 영역 안에 둔다(가장자리는 잘릴 수 있음). 배경은 전체를 꽉 채운다.
"""

def _clean(svg: str) -> str:
    a, b = svg.find("<svg"), svg.rfind("</svg>")
    if a < 0 or b < 0:
        raise ValueError("SVG 없음/미완성")
    svg = svg[a: b + 6]
    svg = re.sub(r"<(text|script|image|foreignObject)\b.*?</\1>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<(text|script|image|foreignObject)\b[^>]*/>", "", svg, flags=re.I)
    svg = re.sub(r"(xlink:)?href\s*=\s*\"(?!#)[^\"]*\"", "", svg)
    return svg

def _one(issue: dict, color: str, dest: str):
    import cairosvg
    client = anthropic.Anthropic()
    msg = client.messages.create(model=MODEL, max_tokens=12000, messages=[{"role": "user", "content": PROMPT.format(
        category=issue["category"], title=issue["title"], subtitle=issue.get("subtitle", ""),
        summary=issue.get("summary", ""), color=color, w=W, h=H)}])
    raw = "".join(b.text for b in msg.content if b.type == "text")
    try:
        svg = _clean(raw)
    except Exception as e:
        raise RuntimeError(f"{e} | stop={msg.stop_reason} len={len(raw)} head={raw[:200]!r}")
    try:
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=dest, output_width=W, output_height=H)
    except Exception as e:
        raise RuntimeError(f"렌더 실패 {e} | len={len(svg)} head={svg[:150]!r} tail={svg[-150:]!r}")
    return dest

def make_all(issues: list, outdir: str, colors: dict) -> dict:
    """{이슈번호: PNG경로}. 개별 실패는 건너뛴다. 파일명이 'ill'로 시작해 사진과 구분된다."""
    res = {}
    def job(i, x):
        try:
            return i, _one(x, colors.get(x["category"], "#58A6FF"), os.path.join(outdir, f"ill{i:02d}.png"))
        except Exception as e:
            print(f"일러스트 {i} 실패(사진으로 대체):", e)
            return i, None
    try:
        with cf.ThreadPoolExecutor(max_workers=5) as ex:
            for i, p in ex.map(lambda t: job(*t), enumerate(issues, 1)):
                if p:
                    res[i] = p
    except Exception as e:
        print("일러스트 생성 중단:", e)
    print(f"일러스트 {len(res)}/{len(issues)}개 생성")
    return res

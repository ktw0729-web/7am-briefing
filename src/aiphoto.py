"""이슈별 '사실적인 장면' 이미지를 Cloudflare Workers AI(FLUX.1 schnell)로 만든다. 무료 일일 한도(10,000 Neurons) 안에서 동작.
- CF_ACCOUNT_ID·CF_API_TOKEN이 없거나 생성에 실패하면 빈 값 -> 기존 방식(스톡 사진/분야 색상 배경)으로 대체된다.
- 무료 한도를 넘으면 Cloudflare가 오류를 돌려줄 뿐 과금되지 않는다(무료 플랜).
- 생성 이미지는 실제 사진이 아니므로 파일명을 'ai'로 시작하게 하고, 카드·영상에 'AI 생성 이미지'를 표시한다."""
import os, base64, requests, concurrent.futures as cf

MODEL = "@cf/black-forest-labs/flux-1-schnell"
STEPS = 4   # 1024x1024 한 장 약 170 Neurons -> 하루 3판 x 10건이어도 무료 한도 안
STYLE = ("Photorealistic editorial news photograph, natural light, documentary style, 35mm lens, realistic colors. "
         "No text, no letters, no numbers, no signs, no signboards, no logos, no flags, no watermark. "
         "No recognizable real people; people only as anonymous figures seen from behind or far away.")
FALLBACK = {   # 요약에 scene이 없을 때(샘플 데이터 등) 분야별 기본 장면
    "경제": "A busy downtown financial district street in Seoul at morning rush hour, glass office towers",
    "산업": "Inside a modern factory with robotic arms and workers in safety gear seen from behind",
    "국제": "Rows of shipping containers and cargo cranes at a large international port under a cloudy sky",
    "기술": "Close-up of a semiconductor wafer and circuit boards on a clean-room workbench, cool blue light",
    "사회": "A crowded city crosswalk in South Korea with anonymous pedestrians in coats, seen from a distance",
}

def enabled() -> bool:
    return bool(os.getenv("CF_ACCOUNT_ID") and os.getenv("CF_API_TOKEN"))

def _one(prompt: str, dest: str) -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CF_ACCOUNT_ID']}/ai/run/{MODEL}"
    r = requests.post(url, headers={"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}"},
                      json={"prompt": prompt[:2000], "steps": STEPS}, timeout=120)
    try:
        j = r.json()
    except ValueError:
        raise RuntimeError(f"HTTP {r.status_code} {r.text[:150]}")
    if not j.get("success") or not (j.get("result") or {}).get("image"):
        raise RuntimeError(f"HTTP {r.status_code} {str(j.get('errors'))[:200]}")
    with open(dest, "wb") as f:
        f.write(base64.b64decode(j["result"]["image"]))
    return dest

def make_all(issues: list, outdir: str, skip=()) -> dict:
    """{이슈번호: [이미지 경로]}. skip에 든 번호(이미 사진/일러스트가 있는 이슈)는 만들지 않는다. 개별 실패는 건너뛴다."""
    res = {}
    def job(i, x):
        scene = (x.get("scene") or "").strip() or FALLBACK.get(x.get("category"), FALLBACK["사회"])
        try:
            return i, _one(f"{scene}. {STYLE}", os.path.join(outdir, f"ai{i:02d}.jpg"))
        except Exception as e:
            print(f"AI 이미지 {i} 실패(기존 방식으로 대체):", e)
            return i, None
    targets = [(i, x) for i, x in enumerate(issues, 1) if i not in set(skip)]
    try:
        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            for i, p in ex.map(lambda t: job(*t), targets):
                if p:
                    res[i] = [p]
    except Exception as e:
        print("AI 이미지 생성 중단:", e)
    print(f"AI 이미지 {len(res)}/{len(targets)}개 생성")
    return res

def is_ai(path) -> bool:
    return bool(path) and os.path.basename(str(path)).startswith("ai")

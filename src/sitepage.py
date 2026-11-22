"""브리핑 상세 웹페이지 생성 + GitHub Pages(pages 브랜치) 게시. 주소: https://<owner>.github.io/<repo>/<날짜_판>/"""
import glob, html, json, os, re, shutil, subprocess, tempfile
from PIL import Image

OG_W = 1200

def _jpg(src, dst, width=900, q=82):
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)))
    im.save(dst, "JPEG", quality=q, optimize=True)

def _paras(text):
    ps = [p.strip() for p in re.split(r"\n\s*\n|\n", (text or "").strip()) if p.strip()]
    if len(ps) <= 1:
        s = [x for x in re.split(r"(?<=[.!?。])\s+", (text or "").strip()) if x]
        ps = [" ".join(s[i:i + 2]) for i in range(0, len(s), 2)] or ps
    return ps

CSS = """
*{box-sizing:border-box}body{margin:0;background:#FAF6EF;color:#1c1b1a;font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif;line-height:1.75;-webkit-text-size-adjust:100%}
#bar{position:fixed;top:0;left:0;height:4px;width:0;background:#2F7DE1;z-index:9}
header{background:#F4EFE6;border-bottom:1px solid #e6dfd2;padding:18px 20px}
.w{max-width:720px;margin:0 auto}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:22px;color:#1d63c7;text-decoration:none}
.logo{width:34px;height:34px;border-radius:9px;background:#2F7DE1;display:inline-block}
.meta{text-align:right;font-size:13px;color:#6b665e}.meta b{display:block;font-size:16px;color:#1c1b1a}.meta b i{font-style:normal;color:#2F7DE1}
.nav{padding:14px 20px 0}.nav a{color:#1d63c7;font-size:14px;margin-right:14px;text-decoration:none}
article{padding:34px 20px 8px;border-bottom:1px solid #e9e2d6}
.hd{display:flex;gap:12px;align-items:flex-start}
.no{flex:none;background:#E7EEFA;color:#1d63c7;font-weight:800;font-size:15px;border-radius:9px;padding:4px 10px;margin-top:3px}
h2{margin:0;font-size:22px;line-height:1.4;flex:1}
.cat{flex:none;font-size:13px;font-weight:700;margin-top:6px}
.sub{color:#6b665e;margin:8px 0 16px 0;font-size:16px}
figure{margin:0 0 18px}figure img{width:100%;display:block;border-radius:20px;background:#eee}
p{margin:0 0 16px;font-size:17px}
.src{font-size:13px;color:#8a847a;margin:0 0 30px}
.credit{font-size:12px;color:#9a948a;margin:-8px 0 14px}
footer{padding:28px 20px 60px;color:#8a847a;font-size:13px}
.vid{display:inline-block;margin:10px 20px 0;background:#2F7DE1;color:#fff;padding:8px 14px;border-radius:999px;text-decoration:none;font-size:14px}
ul.l{list-style:none;padding:0;margin:20px 20px}ul.l li{padding:14px 0;border-bottom:1px solid #e9e2d6}ul.l a{color:#1c1b1a;text-decoration:none;font-weight:700}ul.l span{color:#8a847a;font-size:13px;margin-left:8px}
"""
JS = "<script>addEventListener('scroll',function(){var h=document.documentElement;document.getElementById('bar').style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight)*100)+'%'})</script>"

def _page(title, desc, og, canonical, body):
    e = html.escape
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta property="og:type" content="article"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(og)}"><meta property="og:url" content="{e(canonical)}"><meta property="og:site_name" content="데일리브리핑">
<meta name="twitter:card" content="summary_large_image"><style>{CSS}</style></head><body><div id="bar"></div>{body}{JS}</body></html>"""

def render(date_str, edition_name, intro, issues, imgs, colors, base, dirname, video_url="", credit="", prev_note=""):
    e = html.escape
    arts = []
    for i, x in enumerate(issues, 1):
        col = colors.get(x["category"], "#555")
        fig = f'<figure><img src="{imgs[i]}" alt="" loading="lazy"></figure>' if i in imgs else ""
        ps = "".join(f"<p>{e(p)}</p>" for p in _paras(x.get("narration", "")))
        src = ", ".join(x.get("sources", []))
        arts.append(f'<article id="i{i}"><div class="w"><div class="hd"><span class="no">{i:02d}</span><h2>{e(x["title"])}</h2>'
                    f'<span class="cat" style="color:{col}">{e(x["category"])}</span></div><div class="sub">{e(x["subtitle"])}</div>'
                    f'{fig}{ps}<div class="src">참고: {e(src)}</div></div></article>')
    vid = f'<a class="vid" href="{e(video_url)}">▶ 영상으로 보기</a>' if video_url else ""
    body = (f'<header><div class="w top"><a class="brand" href="../"><span class="logo"></span>데일리브리핑</a>'
            f'<div class="meta">{e(date_str)} · {e(edition_name)}<b>오늘의 이슈 <i>{len(issues)}</i>가지</b></div></div></header>'
            f'<div class="w nav"><a href="../">지난 브리핑</a></div>{vid}'
            + "".join(arts) +
            f'<footer><div class="w">{e(intro)}<br><br>AI가 여러 언론 보도를 바탕으로 요약·재작성한 브리핑이며, 사실관계는 원문 보도를 확인해 주세요.'
            f'{("<br>" + e(credit)) if credit else ""}</div></footer>')
    return _page(f"{date_str} {edition_name} — 데일리브리핑", " · ".join(x["title"] for x in issues[:3]) + " 외", f"{base}{dirname}/og.jpg", f"{base}{dirname}/", body)

def render_index(entries, base):
    e = html.escape
    lis = "".join(f'<li><a href="{e(d)}/">{e(t)}</a><span>{e(n)}</span></li>' for d, t, n in entries)
    body = ('<header><div class="w top"><a class="brand" href="./"><span class="logo"></span>데일리브리핑</a>'
            '<div class="meta">하루 3번 브리핑<b>굿모닝 · 정오 · 굿나잇</b></div></div></header>'
            f'<div class="w"><ul class="l">{lis}</ul></div>')
    return _page("데일리브리핑 — 하루 3번 핵심 뉴스", "굿모닝·정오·굿나잇, 하루 세 번 핵심 이슈 10가지", f"{base}og.jpg", base, body)

def publish(out, dirname, date_str, edition_name, intro, issues, photos, colors, video_url="", credit="", thumb=None):
    """photos: {이슈번호: [이미지경로]}. 성공하면 페이지 URL, 실패하면 ''."""
    repo, tok = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    try:
        owner, name = (repo or "ktw0729-web/7am-briefing").split("/")
        base = f"https://{owner.lower()}.github.io/{name}/"
        site = os.path.join(out, "site", dirname); os.makedirs(site, exist_ok=True)
        imgs = {}
        for i, ps in photos.items():
            if ps and os.path.exists(ps[0]):
                _jpg(ps[0], f"{site}/{i:02d}.jpg"); imgs[i] = f"{i:02d}.jpg"
        og_src = thumb if thumb and os.path.exists(thumb) else None
        if og_src:
            _jpg(og_src, f"{site}/og.jpg", OG_W, 85)
        open(f"{site}/index.html", "w", encoding="utf-8").write(
            render(date_str, edition_name, intro, issues, imgs, colors, base, dirname, video_url, credit))
        if not (repo and tok):
            print("사이트 페이지 로컬 생성:", site); return ""
        tmp = tempfile.mkdtemp(); env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        url = f"https://x-access-token:{tok}@github.com/{repo}.git"
        def git(*a, check=True):
            return subprocess.run(["git", *a], cwd=tmp, check=check, env=env, capture_output=True, text=True)
        for attempt in range(3):
            shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
            if git("clone", "-q", "--depth", "1", "--branch", "pages", url, ".", check=False).returncode != 0:
                git("init", "-q", "-b", "pages"); git("remote", "add", "origin", url)
            git("config", "user.name", "github-actions[bot]"); git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
            dst = os.path.join(tmp, dirname)
            shutil.rmtree(dst, ignore_errors=True); shutil.copytree(site, dst)
            ents = []
            for d in sorted(glob.glob(f"{tmp}/20*_*"), reverse=True):
                m = re.match(r"(\d{4})-(\d\d)-(\d\d)_(\w+)", os.path.basename(d))
                if m and os.path.exists(f"{d}/index.html"):
                    ed = {"morning": "굿모닝 브리핑", "noon": "정오 브리핑", "evening": "굿나잇 브리핑"}.get(m.group(4), m.group(4))
                    ents.append((os.path.basename(d), f"{m.group(1)}.{int(m.group(2))}.{int(m.group(3))} {ed}", ""))
            open(f"{tmp}/index.html", "w", encoding="utf-8").write(render_index(ents, base))
            if og_src and not os.path.exists(f"{tmp}/og.jpg"):
                shutil.copy(f"{site}/og.jpg", f"{tmp}/og.jpg")
            open(f"{tmp}/.nojekyll", "w").close()
            git("add", "-A"); git("commit", "-q", "-m", f"page {dirname}", check=False)
            if git("push", "-q", "origin", "pages", check=False).returncode == 0:
                return f"{base}{dirname}/"
        print("사이트 페이지 푸시 실패")
    except Exception as ex:
        print("사이트 페이지 게시 실패(링크 없이 진행):", getattr(ex, "stderr", ex))
    return ""

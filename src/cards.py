"""영상 프레임(1920x1080) 생성: 왼쪽 제목/부제, 오른쪽 이미지, 하단 자막."""
import glob, os
from PIL import Image, ImageDraw, ImageFont
import brand

W, H = 1920, 1080
COLORS = {"경제": "#E8590C", "산업": "#1971C2", "국제": "#2F9E44", "기술": "#7048E8", "사회": "#C2255C"}
PANEL = (1130, 175, 1830, 700)           # 오른쪽 이미지 영역 (700x550)
_cache = {}

def _font(size, bold=False):
    k = (size, bold)
    if k not in _cache:
        cands = glob.glob("/usr/share/fonts/**/NotoSansCJK-*.ttc", recursive=True) + \
                glob.glob("/usr/share/fonts/**/NanumGothic*.ttf", recursive=True) + \
                glob.glob("C:/Windows/Fonts/malgun*.ttf") + glob.glob("/System/Library/Fonts/AppleSDGothicNeo*")
        pick = [c for c in cands if ("Bold" in c) == bold] or cands
        _cache[k] = ImageFont.truetype(pick[0], size)
    return _cache[k]

from PIL import ImageFilter
BG_TOP, BG_BOT, ROW = (11, 15, 20), (22, 29, 38), "#1A222C"

def bg_canvas(w, h, color):
    """위→아래로 살짝 밝아지는 그라데이션 + 분야 색상의 은은한 빛(왼쪽 위). 모든 화면이 같은 분위기를 갖게 하는 공통 배경."""
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        base.putpixel((0, y), tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img = base.resize((w, h))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-w * 0.35, -h * 0.55, w * 0.55, h * 0.35], fill=color + "40" if color.startswith("#") and len(color) == 7 else color)
    glow = glow.filter(ImageFilter.GaussianBlur(min(w, h) * 0.12))
    return Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

def brand_mark(d, x, y, size=34, color="#58A6FF", anchor_right=False):
    """작은 색 사각형 + '데일리브리핑' 워드마크 (모든 화면 같은 위치·모양)."""
    f = _font(size, True)
    tw = int(d.textlength(brand.BRAND, font=f))
    box = size + 14
    total = box + tw
    x0 = x - total if anchor_right else x
    d.rounded_rectangle([x0, y, x0 + int(size * 0.72), y + int(size * 0.72)], int(size * 0.18), fill=color)
    d.text((x0 + int(size * 0.72) + 12, y + int(size * 0.36)), brand.BRAND, font=f, fill="#E6EDF3", anchor="lm")

def progress(d, x, y, w, idx, total, color, h=8, gap=8):
    """이슈 진행 표시: total칸 중 idx번째까지 색칠."""
    seg = (w - gap * (total - 1)) / total
    for i in range(total):
        x0 = x + i * (seg + gap)
        d.rounded_rectangle([x0, y, x0 + seg, y + h], h // 2, fill=color if i < idx else "#2A333D")

def shadow(img, box, r, blur=28, offset=14, alpha=140):
    """사진 패널 아래 부드러운 그림자."""
    x0, y0, x1, y1 = box
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + offset, x1, y1 + offset], r, fill=(0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"))

def _wrap(draw, text, font, width):
    """단어(띄어쓰기) 단위로 줄바꿈, 한 단어가 너무 길면 글자 단위로."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
            continue
        if cur:
            lines.append(cur); cur = ""
        for ch in word:
            if draw.textlength(cur + ch, font=font) > width:
                lines.append(cur); cur = ch
            else:
                cur += ch
    return lines + ([cur] if cur else [])

def _cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))

def _paste_panel(img, photo, color):
    x0, y0, x1, y1 = PANEL
    w, h = x1 - x0, y1 - y0
    if photo:
        pic = _cover(Image.open(photo).convert("RGB"), w, h)
    else:  # 사진이 없을 때: 분야 색상의 추상 일러스트
        pic = Image.new("RGB", (w, h), color)
        d = ImageDraw.Draw(pic, "RGBA")
        d.ellipse([w * 0.45, -h * 0.25, w * 1.3, h * 0.6], fill=(255, 255, 255, 40))
        d.ellipse([-w * 0.2, h * 0.5, w * 0.5, h * 1.3], fill=(0, 0, 0, 45))
        d.ellipse([w * 0.3, h * 0.3, w * 0.75, h * 0.8], fill=(255, 255, 255, 30))
    shadow(img, PANEL, 36)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], 36, fill=255)
    img.paste(pic, (x0, y0), mask)

def _caption(img, text):
    """인트로/아웃트로용 하단 자막 (왼쪽 정렬)."""
    if not text:
        return
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([90, 790, W - 90, 1000], 28, fill=(0, 0, 0, 175))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))
    d = ImageDraw.Draw(img)
    f = _font(56, True)
    y = 830
    for ln in _wrap(d, text, f, W - 260)[:2]:
        d.text((130, y), ln, font=f, fill="white"); y += 76

NARR_BOX = (100, 735, 1820, 1005)   # 기사 본문(나레이션) 영역: 왼쪽 정렬, 한 페이지에 전부 표시

def _fit_text(d, units, cur):
    """units: [(문장, 단락번호)]. 단락마다 줄을 바꾸고 단락 사이를 띄워, 박스 안에 전부 들어가도록 글자 크기를 조절.
    현재 읽는 문장(cur)만 강조."""
    x0, y0, x1, y1 = NARR_BOX
    units = [(u, 0) if isinstance(u, str) else u for u in units]
    tokens = [(w, k, para) for k, (u, para) in enumerate(units) for w in u.split(" ") if w]
    for size in range(58, 21, -2):
        f, lh = _font(size, False), int(size * 1.35)
        gap = int(size * 0.8)
        sp = d.textlength(" ", font=f)
        lines, cur_line, cur_w, last_para = [], [], 0, None   # lines: (토큰목록, 단락시작여부)
        for w, k, para in tokens:
            new_para = para != last_para
            ww = d.textlength(w, font=f)
            if cur_line and (new_para or cur_w + sp + ww > x1 - x0):
                lines.append((cur_line, cur_start)); cur_line, cur_w = [], 0
            if not cur_line:
                cur_start = new_para and last_para is not None
            cur_w += (sp if cur_line else 0) + ww
            cur_line.append((w, k)); last_para = para
        if cur_line:
            lines.append((cur_line, cur_start))
        height = len(lines) * lh + gap * sum(1 for _, st in lines if st)
        if height <= y1 - y0:
            break
    y = y0
    for line, starts_para in lines:
        if starts_para:
            y += gap
        x = x0
        for w, k in line:
            on = cur is None or k == cur   # cur=None: 전부 흰색
            fnt = _font(size, True) if on else f
            d.text((x, y), w, font=fnt, fill="white" if on else "#6E7681")
            x += d.textlength(w, font=fnt) + sp
        y += lh

def issue_frame(path, idx, total, issue, date_str, units=(), cur=-1, photo=None, photo_credit=''):
    color = COLORS.get(issue["category"], "#555")
    img = bg_canvas(W, H, color)
    d = ImageDraw.Draw(img)
    brand_mark(d, 100, 62, 38, color)
    d.text((W - 100, 82), f"{date_str}  ·  {brand.current['name']}", font=_font(36), fill="#8B949E", anchor="rm")
    progress(d, 100, 128, W - 200, idx, total, color, h=6)
    pw = int(d.textlength(issue["category"], font=_font(48, True))) + 70
    d.rounded_rectangle([100, 190, 100 + pw, 270], 40, fill=color)
    d.text((100 + pw // 2, 230), issue["category"], font=_font(48, True), fill="white", anchor="mm")
    y = 310
    for ln in _wrap(d, issue["title"], _font(80, True), 960)[:3]:
        d.text((100, y), ln, font=_font(80, True), fill="white"); y += 100
    y += 20
    for ln in _wrap(d, issue["subtitle"], _font(44), 960)[:2]:
        d.text((100, y), ln, font=_font(44), fill="#C9D1D9"); y += 62
    _paste_panel(img, photo, color)
    d.line([100, 722, 1820, 722], fill="#2A333D", width=2)
    _fit_text(d, list(units), cur)
    src = ", ".join(issue.get("sources", []))[:50]
    if src:
        d.text((100, H - 35), f"참고: {src}", font=_font(28), fill="#6E7681", anchor="lm")
    if photo and photo_credit and "ill" not in os.path.basename(photo):
        d.text((W - 100, H - 35), f"Photos: {photo_credit}", font=_font(28), fill="#6E7681", anchor="rm")
    img.save(path)

def title_frame(path, date_str, sub="", caption=""):
    img = bg_canvas(W, H, "#58A6FF")
    d = ImageDraw.Draw(img)
    bw = int(d.textlength(brand.BRAND, font=_font(48, True))) + 34 + 12
    brand_mark(d, W // 2 - bw // 2, 190, 48)
    d.rounded_rectangle([W // 2 - 60, 560, W // 2 + 60, 566], 3, fill="#58A6FF")
    d.text((W // 2, 350), brand.current["name"], font=_font(130, True), fill="white", anchor="mm")
    d.text((W // 2, 470), date_str, font=_font(64), fill="#58A6FF", anchor="mm")
    if sub:
        d.text((W // 2, 640), sub, font=_font(44), fill="#8B949E", anchor="mm")
    _caption(img, caption)
    img.save(path)

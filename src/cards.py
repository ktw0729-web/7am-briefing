"""이슈 카드 이미지(1920x1080) 생성."""
import glob, textwrap
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
COLORS = {"경제": "#E8590C", "산업": "#1971C2", "국제": "#2F9E44", "기술": "#7048E8", "사회": "#C2255C"}

def _font(size, bold=False):
    cands = glob.glob("/usr/share/fonts/**/NotoSansCJK-*.ttc", recursive=True) + \
            glob.glob("/usr/share/fonts/**/NanumGothic*.ttf", recursive=True) + \
            glob.glob("C:/Windows/Fonts/malgun*.ttf") + glob.glob("/System/Library/Fonts/AppleSDGothicNeo*")
    pick = [c for c in cands if ("Bold" in c) == bold] or cands
    return ImageFont.truetype(pick[0], size)

def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > width:
            lines.append(cur); cur = ch
        else:
            cur += ch
    return lines + ([cur] if cur else [])

def issue_card(path, idx, total, issue, date_str):
    img = Image.new("RGB", (W, H), "#101418")
    d = ImageDraw.Draw(img)
    color = COLORS.get(issue["category"], "#555")
    d.rectangle([0, 0, 24, H], fill=color)
    d.text((100, 80), f"{date_str}  ·  7시 브리핑  {idx}/{total}", font=_font(40), fill="#8B949E")
    d.rounded_rectangle([100, 190, 100 + 60 + 52 * len(issue["category"]), 270], 40, fill=color)
    d.text((130, 200), issue["category"], font=_font(48, True), fill="white")
    y = 330
    for ln in _wrap(d, issue["title"], _font(96, True), W - 260):
        d.text((100, y), ln, font=_font(96, True), fill="white"); y += 120
    y += 30
    for ln in _wrap(d, issue["subtitle"], _font(54), W - 260):
        d.text((100, y), ln, font=_font(54), fill="#C9D1D9"); y += 76
    src = ", ".join(issue.get("sources", []))[:60]
    if src:
        d.text((100, H - 100), f"참고: {src}", font=_font(34), fill="#6E7681")
    img.save(path)

def title_card(path, text, date_str, sub=""):
    img = Image.new("RGB", (W, H), "#101418")
    d = ImageDraw.Draw(img)
    d.text((W // 2, 400), "7시 브리핑", font=_font(140, True), fill="white", anchor="mm")
    d.text((W // 2, 570), date_str, font=_font(64), fill="#58A6FF", anchor="mm")
    if sub:
        d.text((W // 2, 700), sub, font=_font(44), fill="#8B949E", anchor="mm")
    img.save(path)

"""Threads용 세로형 카드뉴스(1080x1350) 생성: 표지 + 이슈별 카드 + 마지막 안내 카드."""
from PIL import Image, ImageDraw
from cards import _font, _wrap, _cover, COLORS
import brand

CW, CH = 1080, 1350
BG, SUB, DIM = "#101418", "#C9D1D9", "#6E7681"

def _round_paste(img, pic, box, r=40):
    x0, y0, x1, y1 = box
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, x1 - x0, y1 - y0], r, fill=255)
    img.paste(pic, (x0, y0), mask)

def _illustration(w, h, color):
    pic = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(pic, "RGBA")
    d.ellipse([w * 0.5, -h * 0.4, w * 1.25, h * 0.7], fill=(255, 255, 255, 40))
    d.ellipse([-w * 0.2, h * 0.45, w * 0.45, h * 1.4], fill=(0, 0, 0, 45))
    d.ellipse([w * 0.3, h * 0.2, w * 0.7, h * 0.9], fill=(255, 255, 255, 28))
    return pic

def cover(path, date_str, issues):
    img = Image.new("RGB", (CW, CH), BG); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 20, CH], fill="#58A6FF")
    d.text((80, 110), date_str, font=_font(44), fill="#58A6FF")
    d.text((80, 190), brand.current["name"], font=_font(104, True), fill="white")
    d.text((80, 330), f"{brand.BRAND}  ·  오늘의 핵심 이슈 {len(issues)}개", font=_font(44), fill="#8B949E")
    y = 450
    for i, x in enumerate(issues, 1):
        col = COLORS.get(x["category"], "#555")
        d.rounded_rectangle([80, y, 80 + 120, y + 56], 28, fill=col)
        d.text((140, y + 28), x["category"], font=_font(32, True), fill="white", anchor="mm")
        t = _wrap(d, x["title"], _font(38, True), 780)[0]
        if t != x["title"]:
            t = t[:-1] + "…"
        d.text((225, y + 28), t, font=_font(38, True), fill="white", anchor="lm")
        y += 82
    d.text((CW - 80, CH - 70), "옆으로 넘겨 보세요 ▶", font=_font(34), fill=DIM, anchor="rm")
    img.save(path)

def issue_card(path, idx, total, issue, date_str, photo=None, credit=""):
    img = Image.new("RGB", (CW, CH), BG); d = ImageDraw.Draw(img)
    col = COLORS.get(issue["category"], "#555")
    d.rectangle([0, 0, 20, CH], fill=col)
    box = (60, 60, CW - 60, 520)
    w, h = box[2] - box[0], box[3] - box[1]
    pic = _cover(__import__("PIL.Image", fromlist=["Image"]).open(photo).convert("RGB"), w, h) if photo \
        else _illustration(w, h, col)
    _round_paste(img, pic, box)
    pw = int(d.textlength(issue["category"], font=_font(40, True))) + 60
    d.rounded_rectangle([80, 560, 80 + pw, 632], 36, fill=col)
    d.text((80 + pw // 2, 596), issue["category"], font=_font(40, True), fill="white", anchor="mm")
    d.text((CW - 80, 596), f"{idx} / {total}", font=_font(38), fill=DIM, anchor="rm")
    y = 670
    for ln in _wrap(d, issue["title"], _font(60, True), CW - 160)[:3]:
        d.text((80, y), ln, font=_font(60, True), fill="white"); y += 78
    y += 10
    for ln in _wrap(d, issue["subtitle"], _font(38, True), CW - 160)[:2]:
        d.text((80, y), ln, font=_font(38, True), fill=col if col != "#101418" else SUB); y += 54
    y += 18
    for ln in _wrap(d, issue["summary"], _font(36), CW - 160)[:6]:
        d.text((80, y), ln, font=_font(36), fill=SUB); y += 54
    src = ", ".join(issue.get("sources", []))[:40]
    foot = f"참고: {src}" if src else ""
    d.text((80, CH - 60), foot, font=_font(28), fill=DIM, anchor="lm")
    d.text((CW - 80, CH - 60), f"{date_str} {brand.current['name']}" + (f" · Photo: {credit}" if photo and credit else ""),
           font=_font(28), fill=DIM, anchor="rm")
    img.save(path)

def outro(path, date_str):
    img = Image.new("RGB", (CW, CH), BG); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 20, CH], fill="#58A6FF")
    d.text((CW // 2, 520), brand.BRAND, font=_font(110, True), fill="white", anchor="mm")
    d.text((CW // 2, 650), "아침5분 · 정오 · 굿나잇  하루 3번 브리핑", font=_font(44), fill="#58A6FF", anchor="mm")
    d.text((CW // 2, 1150), "※ 언론 보도를 AI로 요약·재구성한 콘텐츠입니다.", font=_font(32), fill=DIM, anchor="mm")
    d.text((CW // 2, 1205), "정확한 내용은 각 언론사 원문을 확인해 주세요.", font=_font(32), fill=DIM, anchor="mm")
    img.save(path)

def build(outdir, date_str, issues, photos_by_issue, credit=""):
    import os
    os.makedirs(outdir, exist_ok=True)
    cover(f"{outdir}/00_cover.png", date_str, issues)
    for i, x in enumerate(issues, 1):
        ph = photos_by_issue.get(i) or []
        issue_card(f"{outdir}/{i:02d}.png", i, len(issues), x, date_str, ph[0] if ph else None, credit)
    outro(f"{outdir}/99_outro.png", date_str)
    # 스레드 본문 텍스트(복사해서 쓰기용)
    head = f"📰 {date_str} {brand.current['name']}\n오늘의 핵심 이슈 {len(issues)}개\n\n" + "\n".join(
        f"{i}. [{x['category']}] {x['title']}" for i, x in enumerate(issues, 1))
    open(f"{outdir}/threads_text.txt", "w", encoding="utf-8").write(head)

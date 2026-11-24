"""나라장터 입찰공고 조회 (공공데이터포털 '조달청_나라장터 입찰공고정보서비스', End Point .../BidPublicInfoService02).

수요기관이 '조달청'(본청) 또는 '대전광역시'(본청)인 공고를 출력한다. (정확히 일치; 지방조달청·자치구·교육청 등은 제외)
추가로 전국 모든 수요기관의 '대형 SI·SM 용역'(사업명 키워드 + 추정금액 30억 원 이상)을 별도 구역으로 출력한다.

사용법:
    export G2B_SERVICE_KEY="일반인증키(Decoding)"
    python scripts/nara_g2b.py --days 1 --format md
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService02"
OPS = {
    "용역": ["getBidPblancListInfoServc02", "getBidPblancListInfoServc"],
    "물품": ["getBidPblancListInfoThng02", "getBidPblancListInfoThng"],
    "공사": ["getBidPblancListInfoCnstwk02", "getBidPblancListInfoCnstwk"],
}
ORGS = {"조달청", "대전광역시"}
BIG_WON = 3_000_000_000  # 대형 기준: 추정금액 30억 원 이상
SISM_TITLE = "대형 SI·SM 용역 (전국, 추정 30억원 이상)"
# 사업명에 'IT 대상어' 와 '구축/유지관리 행위어'가 함께 있어야 SI·SM 으로 본다. 나라장터에 SI/SM 분류는 없어 글자로 추정한다.
IT_WORDS = ("정보시스템", "정보화", "시스템", "소프트웨어", "플랫폼", "전산", "정보통신", "클라우드",
            "데이터", "빅데이터", "인공지능", "AI", "ISP", "차세대", "포털", "웹", "앱", "SW", "DB", "네트워크")
SM_WORDS = ("유지관리", "유지보수", "운영", "위탁", "SM")
SI_WORDS = ("구축", "개발", "고도화", "재구축", "통합", "이전", "전환", "개선", "확장")
KST = timezone(timedelta(hours=9))
ROWS = 999
MAX_PAGES = 30


def _call(kind, params):
    last = None
    for op in OPS[kind]:
        url = f"{BASE}/{op}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                raw = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            last = f"{op}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}"
            print(f"[시도 실패] {last}", file=sys.stderr)
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            last = f"{op}: JSON 아님 -> {raw[:300]}"
            print(f"[시도 실패] {last}", file=sys.stderr)
            continue
        resp = data.get("response", data)
        hdr = resp.get("header", {})
        if str(hdr.get("resultCode", "00")) not in ("00", "0"):
            last = f"{op}: resultCode={hdr.get('resultCode')} {hdr.get('resultMsg', '')}"
            print(f"[시도 실패] {last}", file=sys.stderr)
            continue
        body = resp.get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if not isinstance(items, list):
            items = [items]
        OPS[kind] = [op]  # 성공한 이름만 이후 페이지에 사용
        return items, int(body.get("totalCount", 0) or 0)
    sys.exit(f"{kind} 조회 실패: {last}")


def fetch_all(kind, days, key):
    end = datetime.now(KST)
    bgn = end - timedelta(days=days)
    out, page, total = [], 1, None
    while page <= MAX_PAGES:
        params = {
            "serviceKey": key, "pageNo": page, "numOfRows": ROWS, "type": "json",
            "inqryDiv": 1,  # 1=공고게시일시 기준
            "inqryBgnDt": bgn.strftime("%Y%m%d%H%M"),
            "inqryEndDt": end.strftime("%Y%m%d%H%M"),
        }
        items, total = _call(kind, params)
        out += items
        if not items or len(out) >= total:
            break
        page += 1
    print(f"[{kind}] 전체 {total}건 중 {len(out)}건 조회", file=sys.stderr)
    return out


def org_of(it):
    return (it.get("dminsttNm") or it.get("ntceInsttNm") or "").strip()


def select(items):
    rows = []
    for it in items:
        org = org_of(it)
        if org not in ORGS:
            continue
        rows.append({
            "수요기관": org,
            "공고번호": f"{it.get('bidNtceNo', '')}-{it.get('bidNtceOrd', '')}",
            "사업명": (it.get("bidNtceNm") or "").strip(),
            "추정가격": it.get("presmptPrce") or "",
            "공고일시": it.get("bidNtceDt", ""),
            "입찰마감": it.get("bidClseDt", ""),
            "개찰일시": it.get("opengDt", ""),
            "링크": it.get("bidNtceDtlUrl", ""),
        })
    return sorted(rows, key=lambda r: r["공고일시"])


def amount_of(it):
    for k in ("presmptPrce", "asmtAmt", "bdgtAmt"):
        try:
            v = float(it.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v > 0:
            return v
    return 0.0


def sism_kind(name):
    """사업명으로 SI/SM 구분. 해당 없으면 None."""
    up = name.upper()
    if not any(w.upper() in up for w in IT_WORDS):
        return None
    sm = any(w.upper() in up for w in SM_WORDS)
    si = any(w in name for w in SI_WORDS)
    if not (sm or si):
        return None
    return "SM" if sm and not si else ("SI·SM" if sm and si else "SI")


def select_sism(items, skip_ids):
    rows = []
    for it in items:
        name = (it.get("bidNtceNm") or "").strip()
        no = f"{it.get('bidNtceNo', '')}-{it.get('bidNtceOrd', '')}"
        amt = amount_of(it)
        kind = sism_kind(name)
        if kind is None or amt < BIG_WON or no in skip_ids:
            continue
        rows.append({
            "수요기관": org_of(it) or "기관 미기재",
            "공고번호": no,
            "사업명": f"[{kind}] {name}",
            "추정가격": amt,
            "공고일시": it.get("bidNtceDt", ""),
            "입찰마감": it.get("bidClseDt", ""),
            "개찰일시": it.get("opengDt", ""),
            "링크": it.get("bidNtceDtlUrl", ""),
        })
    return sorted(rows, key=lambda r: -float(r["추정가격"]))


def money(v):
    try:
        return f"{int(float(v)):,}원"
    except (TypeError, ValueError):
        return "비공개/미기재"


def to_md(results, days):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# 나라장터 공고 (조달청 본청·대전광역시 수요 + 대형 SI·SM) — 최근 {days}일, 조회 {now} KST", ""]
    for kind, rows in results.items():
        lines.append(f"## {kind} ({len(rows)}건)")
        if not rows:
            lines.append("- 해당 공고 없음")
        for r in rows:
            lines.append(
                f"- [{r['수요기관']}] {r['사업명']} / 공고번호 {r['공고번호']} / {money(r['추정가격'])}"
                f" / 마감 {r['입찰마감'] or '-'} / 개찰 {r['개찰일시'] or '-'}"
                + (f" / {r['링크']}" if r["링크"] else ""))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    a = ap.parse_args()
    key = os.environ.get("G2B_SERVICE_KEY") or sys.exit("환경변수 G2B_SERVICE_KEY 가 없습니다.")
    raw = {k: fetch_all(k, a.days, key) for k in ("용역", "물품", "공사")}
    results = {k: select(v) for k, v in raw.items()}
    shown = {r["공고번호"] for rows in results.values() for r in rows}
    results[SISM_TITLE] = select_sism(raw["용역"], shown)
    if a.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        print(to_md(results, a.days))

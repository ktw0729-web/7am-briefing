"""나라장터 입찰공고 조회 (공공데이터포털 '조달청_나라장터 입찰공고정보서비스').

사용법:
    export G2B_SERVICE_KEY="발급받은_일반인증키(Decoding)"
    python nara_g2b.py            # 어제~오늘 게시된 용역 공고 중 키워드 매칭 출력
    python nara_g2b.py --days 3 --kind 공사 --kw 대전

주의: 엔드포인트/파라미터는 data.go.kr 활용신청 상세페이지의 '참고문서'와 다르면 그쪽을 따를 것.
"""
import argparse
import os
import sys
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
OPS = {
    "용역": "getBidPblancListInfoServc",
    "물품": "getBidPblancListInfoThng",
    "공사": "getBidPblancListInfoCnstwk",
}
DEFAULT_KW = ["정보화", "소프트웨어", "SW", "AI", "클라우드", "시스템", "나라장터", "디지털"]


def fetch(kind, days, rows=100, key=None):
    key = key or os.environ.get("G2B_SERVICE_KEY")
    if not key:
        sys.exit("환경변수 G2B_SERVICE_KEY 가 없습니다.")
    end = datetime.now()
    bgn = end - timedelta(days=days)
    params = {
        "serviceKey": key,          # Decoding 키를 넣으면 urlencode가 인코딩함
        "pageNo": 1,
        "numOfRows": rows,
        "type": "json",
        "inqryDiv": 1,              # 1=공고게시일시 기준
        "inqryBgnDt": bgn.strftime("%Y%m%d0000"),
        "inqryEndDt": end.strftime("%Y%m%d2359"),
    }
    url = f"{BASE}/{OPS[kind]}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    body = data.get("response", {}).get("body", {})
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    return items if isinstance(items, list) else [items]


def summarize(items, kws):
    out = []
    for it in items:
        name = it.get("bidNtceNm", "")
        if kws and not any(k.lower() in name.lower() for k in kws):
            continue
        out.append({
            "공고번호": f"{it.get('bidNtceNo', '')}-{it.get('bidNtceOrd', '')}",
            "사업명": name,
            "수요기관": it.get("dminsttNm") or it.get("ntceInsttNm", ""),
            "추정가격": it.get("presmptPrce", ""),
            "공고일시": it.get("bidNtceDt", ""),
            "입찰마감": it.get("bidClseDt", ""),
            "개찰일시": it.get("opengDt", ""),
            "링크": it.get("bidNtceDtlUrl", ""),
        })
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=OPS, default="용역")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--kw", nargs="*", default=DEFAULT_KW)
    a = ap.parse_args()
    res = summarize(fetch(a.kind, a.days), a.kw)
    if not res:
        print("신규 매칭 공고 없음")
    for r in res:
        print(json.dumps(r, ensure_ascii=False))

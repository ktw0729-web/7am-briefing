"""나라장터 사전규격(RFP·규격서)·낙찰·계약 정보 조회 — g2b/extra.md 용.

nara_g2b.py 와 같은 범위(수요기관 조달청 본청·대전광역시 + 전국 대형 SI·SM 용역 30억원 이상), 용역·공사만(물품 제외).
공공데이터포털 서비스 3종(활용신청 필요): 사전규격정보서비스, 낙찰정보서비스, 계약정보서비스.
※ 서비스별 오퍼레이션·필드명을 공식 문서로 확인하지 못해 후보를 순서대로 시도하고, 실패 사유와 응답 필드명을
  실행 로그(stderr)에 남긴다. 조회 실패는 결과 파일에 '조회 실패: 사유'로 표시한다(추측으로 채우지 않음).

사용법: G2B_SERVICE_KEY=... python scripts/nara_g2b_extra.py --days 7
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import time
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nara_g2b as g  # ORGS, KST, BIG_WON, sism_kind, money

ROOT = "https://apis.data.go.kr/1230000"
SERVICES = {
    "사전규격": {
        "bases": [f"{ROOT}/ao/HrcspSsstndrdInfoService", f"{ROOT}/ad/HrcspSsstndrdInfoService"],
        "ops": {"용역": ["getPublicPrcureThngInfoServc"],
                "공사": ["getPublicPrcureThngInfoCnstwk", "getPublicPrcureThngInfoCnstwkPPSSrch"]},
    },
    "낙찰": {
        "bases": [f"{ROOT}/as/ScsbidInfoService", f"{ROOT}/ad/ScsbidInfoService"],
        "ops": {"용역": ["getScsbidListSttusServc", "getScsbidListSttusServcPPSSrch", "getOpengResultListInfoServc"],
                "공사": ["getScsbidListSttusCnstwk", "getScsbidListSttusCnstwkPPSSrch", "getOpengResultListInfoCnstwk"]},
    },
    "계약": {
        "bases": [f"{ROOT}/ao/CntrctInfoService", f"{ROOT}/ad/CntrctInfoService"],
        "ops": {"용역": ["getCntrctInfoListServc", "getCntrctInfoListServcPPSSrch"],
                "공사": ["getCntrctInfoListCnstwk", "getCntrctInfoListCnstwkPPSSrch"]},  # 오퍼레이션명은 공개된 목록으로 확인
    },
}
TITLES = {"사전규격": "사전규격 (RFP 초안·규격서)", "낙찰": "낙찰 결과", "계약": "계약 체결"}
ROWS, MAX_PAGES = 999, 30


def pick(it, *keys):
    for k in keys:
        v = it.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _get(url, tries=3):
    """일시적 네트워크 오류(URLError·타임아웃)는 재시도. HTTPError 는 그대로 올린다."""
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def call(svc, kind, days, key):
    """후보 base×op 를 차례로 시도. 오류이거나 0건이면 다음 후보로. (items, 사용한 op, 오류 요약) 반환."""
    end = datetime.now(g.KST)
    bgn = end - timedelta(days=days)
    errs = []
    empty = None
    for base in SERVICES[svc]["bases"]:
        for op, div in [(o, d) for o in SERVICES[svc]["ops"][kind] for d in (1,)]:
            out, page, total = [], 1, None
            ok = False
            while page <= MAX_PAGES:
                params = {
                    "serviceKey": key, "pageNo": page, "numOfRows": (ROWS if svc == "사전규격" else 100), "type": "json", "inqryDiv": div,
                    "inqryBgnDt": bgn.strftime("%Y%m%d%H%M"), "inqryEndDt": end.strftime("%Y%m%d%H%M"),
                    "inqryBgnDate": bgn.strftime("%Y%m%d"), "inqryEndDate": end.strftime("%Y%m%d"),
                }
                url = f"{base}/{op}?{urllib.parse.urlencode(params)}"
                try:
                    data = json.loads(_get(url))
                except urllib.error.HTTPError as e:
                    hint = " (권한 없음: 활용신청 승인·키 반영 확인)" if e.code in (401, 403) else ""
                    errs.append(f"{base.rsplit('/',1)[-1]}/{op}: HTTP {e.code}{hint}")
                    break
                except Exception as e:  # 네트워크·JSON 오류
                    errs.append(f"{op}: {type(e).__name__}")
                    break
                err = data.get("nkoneps.com.response.ResponseError")
                if err:
                    h = err.get("header", {})
                    errs.append(f"{op}: {h.get('resultCode')} {h.get('resultMsg', '')}")
                    break
                resp = data.get("response", data)
                hdr = resp.get("header", {})
                if str(hdr.get("resultCode", "00")) not in ("00", "0"):
                    errs.append(f"{op}: {hdr.get('resultCode')} {hdr.get('resultMsg', '')}")
                    break
                body = resp.get("body", {})
                items = body.get("items", [])
                if isinstance(items, dict):
                    items = items.get("item", [])
                if not isinstance(items, list):
                    items = [items]
                out += items
                total = int(body.get("totalCount", 0) or 0)
                if page == 1 and not items:
                    print(f"[진단] {svc}/{kind} {op} div={div} 응답: {json.dumps(resp, ensure_ascii=False)[:300]}", file=sys.stderr)
                if not items or len(out) >= total:
                    ok = True
                    break
                page += 1
            if not ok:
                continue
            print(f"[{svc}/{kind}] {op} div={div}: 전체 {total}건 중 {len(out)}건 조회", file=sys.stderr)
            if out:
                print(f"[필드] {svc}/{kind}: {sorted(out[0].keys())}", file=sys.stderr)
                return out, op, ""
            empty = (out, op, "")  # 0건: 다른 후보도 시도
    for e in errs:
        print(f"[시도 실패] {svc}/{kind}: {e}", file=sys.stderr)
    if empty:
        return empty
    return None, "", "; ".join(errs[-3:]) or "응답 없음"


def amount(it):
    for k in ("asignBdgtAmt", "sucsfbidAmt", "totCntrctAmt", "thtmCntrctAmt", "cntrctAmt", "presmptPrce", "bdgtAmt"):
        try:
            v = float(it.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v > 0:
            return v
    return 0.0


def orgs_of(it):
    vals = [pick(it, k) for k in ("rlDminsttNm", "dminsttNm", "orderInsttNm", "ntceInsttNm", "cntrctInsttNm", "dminsttList")]
    return [v for v in vals if v]


def row(svc, it):
    name = pick(it, "bidNtceNm", "cntrctNm", "bfSpecNm", "prdctClsfcNoNm", "bizNm", "cntrctNm")
    no = pick(it, "bfSpecRgstNo", "untyCntrctNo", "bidNtceNo")
    org_list = orgs_of(it)
    links = [v for k, v in it.items() if isinstance(v, str) and v.startswith("http") and "rl" in k.lower()]
    meta = []
    if svc == "사전규격":
        meta = [f"등록 {pick(it, 'rgstDt', 'rcptDt') or '-'}", f"의견마감 {pick(it, 'opninRgstClseDt') or '-'}"]
    elif svc == "낙찰":
        meta = [f"낙찰업체 {pick(it, 'bidwinnrNm', 'sucsfbidCorpNm') or '-'}",
                f"낙찰률 {pick(it, 'sucsfbidRate') or '-'}", f"개찰 {pick(it, 'rlOpengDt', 'opengDt') or '-'}"]
    else:
        meta = [f"체결 {pick(it, 'cntrctCnclsDate', 'cntrctDate') or '-'}",
                f"업체 {pick(it, 'corpList', 'cntrctCorpNm') or '-'}"]
    return org_list, name, no, amount(it), meta, links


def keep(org_list, name, kind, amt):
    if any(o in g.ORGS for o in org_list):
        return True
    return kind == "용역" and amt >= g.BIG_WON and g.sism_kind(name) is not None


def to_md(days, key):
    now = datetime.now(g.KST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# 나라장터 사전규격·낙찰·계약 (조달청 본청·대전광역시 + 대형 SI·SM, 용역·공사) — 최근 {days}일, 조회 {now} KST", ""]
    for svc in SERVICES:
        for kind in ("용역", "공사"):
            items, op, err = call(svc, kind, days, key)
            if items is None:
                lines += [f"## {TITLES[svc]} — {kind} (조회 실패)", f"- 조회 실패: {err}", ""]
                continue
            rows = []
            for it in items:
                org_list, name, no, amt, meta, links = row(svc, it)
                if keep(org_list, name, kind, amt):
                    tag = g.sism_kind(name)
                    rows.append((amt, org_list, f"[{tag}] {name}" if tag and kind == "용역" else name, no, meta, links))
            rows.sort(key=lambda r: -r[0])
            lines.append(f"## {TITLES[svc]} — {kind} ({len(rows)}건)")
            if not rows:
                lines.append("- 해당 건 없음")
            for amt, org_list, name, no, meta, links in rows:
                org = next((o for o in org_list if o in g.ORGS), org_list[0] if org_list else "기관 미기재")
                lines.append(f"- [{org}] {name} / 번호 {no or '-'} / {g.money(amt) if amt else '금액 미기재'} / "
                             + " / ".join(meta) + "".join(f" / {u}" for u in links[:3]))
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    k = os.environ.get("G2B_SERVICE_KEY") or sys.exit("환경변수 G2B_SERVICE_KEY 가 없습니다.")
    print(to_md(a.days, k))

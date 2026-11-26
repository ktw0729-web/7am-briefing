"""나라장터 사전규격(RFP·규격서)·낙찰·계약 정보 조회 — g2b/extra.md 용.

nara_g2b.py 와 같은 범위(수요기관 조달청 본청·대전광역시 + 전국 대형 SI·SM 용역 30억원 이상), 용역·공사만(물품 제외).
공공데이터포털 서비스 3종(활용신청 필요): 사전규격정보서비스, 낙찰정보서비스, 계약정보서비스.
※ 서비스별 오퍼레이션·필드명을 공식 문서로 확인하지 못해 후보를 순서대로 시도하고, 실패 사유와 응답 필드명을
  실행 로그(stderr)에 남긴다. 조회 실패는 결과 파일에 '조회 실패: 사유'로 표시한다(추측으로 채우지 않음).

사용법: G2B_SERVICE_KEY=... python scripts/nara_g2b_extra.py --days 7
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
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
T0 = time.time()
BUDGET = 240  # 초(호출 1회당): 이 시간이 지나면 조회를 멈추고 모은 것만 출력
RESULT_DAYS = 2
WORKERS = 5  # 동시에 받을 쪽 수


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


def _params(key, page, rows, bgn, end, variant):
    prm = {"serviceKey": key, "pageNo": page, "numOfRows": rows, "type": "json", "inqryDiv": 1}
    if variant in ("dt", "both"):
        prm["inqryBgnDt"] = bgn.strftime("%Y%m%d%H%M")
        prm["inqryEndDt"] = end.strftime("%Y%m%d%H%M")
    if variant in ("date", "both"):
        prm["inqryBgnDate"] = bgn.strftime("%Y%m%d")
        prm["inqryEndDate"] = end.strftime("%Y%m%d")
    return prm


def _page(base, op, key, bgn, end, variant, rows, page, errs):
    """한 페이지 조회. 성공하면 (items, total), 오류면 None."""
    url = f"{base}/{op}?{urllib.parse.urlencode(_params(key, page, rows, bgn, end, variant))}"
    try:
        data = json.loads(_get(url))
    except urllib.error.HTTPError as e:
        hint = " (권한 없음: 활용신청 승인·키 반영 확인)" if e.code in (401, 403) else ""
        errs.append(f"{base.rsplit('/',1)[-1]}/{op}: HTTP {e.code}{hint}")
        return None
    except Exception as e:
        errs.append(f"{op}: {type(e).__name__}")
        return None
    err = data.get("nkoneps.com.response.ResponseError")
    if err:
        h = err.get("header", {})
        errs.append(f"{op}[{variant}]: {h.get('resultCode')} {h.get('resultMsg', '')}")
        return None
    resp = data.get("response", data)
    hdr = resp.get("header", {})
    if str(hdr.get("resultCode", "00")) not in ("00", "0"):
        errs.append(f"{op}[{variant}]: {hdr.get('resultCode')} {hdr.get('resultMsg', '')}")
        return None
    body = resp.get("body", {})
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    if not isinstance(items, list):
        items = [items]
    return items, int(body.get("totalCount", 0) or 0)


def _fetch(base, op, key, bgn, end, variant, rows, errs, max_pages=MAX_PAGES):
    """한 기간을 전부 조회. 1쪽으로 총건수를 알고 나머지 쪽은 동시에 받는다. 성공하면 (items, total), 오류면 None."""
    first = _page(base, op, key, bgn, end, variant, rows, 1, errs)
    if first is None:
        return None
    out, total = list(first[0]), first[1]
    last = min(max_pages, -(-total // rows)) if total else 1
    if last > 1 and first[0]:
        def work(pg):
            if time.time() - T0 > BUDGET:
                return pg, "timeout"
            return pg, _page(base, op, key, bgn, end, variant, rows, pg, errs)
        got = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for pg, r in ex.map(work, range(2, last + 1)):
                got[pg] = r
        for pg in range(2, last + 1):
            r = got.get(pg)
            if r == "timeout":
                print(f"[시간 초과] {op}: {pg}쪽/{last}쪽에서 중단", file=sys.stderr)
                break
            if r is None:
                continue
            out += r[0]
    return out, total


def call(svc, kind, days, key):
    """base×op 후보를 차례로. 낙찰·계약은 (기간·날짜파라미터) 조합을 바꿔 가며 되는 방식을 찾는다."""
    global T0
    T0 = time.time()
    end = datetime.now(g.KST)
    errs = []
    empty = None
    if svc != "사전규격":
        days = min(days, RESULT_DAYS)
    if svc == "사전규격":
        combos = [(days, "both", 999)]
    else:
        combos = [(1, "dt", 100), (1, "both", 100), (days, "dt", 100), (days, "date", 100), (days, "both", 10)]
    for base in SERVICES[svc]["bases"]:
        for op in SERVICES[svc]["ops"][kind]:
            for win, variant, rows in combos:
                probe = _fetch(base, op, key, end - timedelta(days=win), end, variant, rows, errs, max_pages=1)
                if probe is None:
                    continue
                print(f"[{svc}/{kind}] {op} 방식 win={win}일 {variant} rows={rows}: 통과", file=sys.stderr)
                out = []
                # 기간이 짧은 방식이면 하루씩 나눠 전체 기간을 채운다
                spans = [(end - timedelta(days=i + win), end - timedelta(days=i)) for i in range(0, days, win)]
                for sb, se in spans:
                    r = _fetch(base, op, key, sb, se, variant, rows, errs)
                    if r:
                        out += r[0]
                print(f"[{svc}/{kind}] {op}: {len(out)}건 조회", file=sys.stderr)
                if out:
                    print(f"[필드] {svc}/{kind}: {sorted(out[0].keys())}", file=sys.stderr)
                    return out, op, ""
                empty = (out, op, "")
                break
    for e in errs[-12:]:
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


def demand_orgs(it):
    """계약의 수요기관(dminsttList) 이름들. '[1^...^기관명^...]' 형태를 구분자로 쪼갠 토큰."""
    import re
    raw = pick(it, "dminsttList")
    return [t.strip() for t in re.split(r"[\^\[\],]", raw) if re.search("[가-힣]", t)]


def is_proxy_contract(it):
    """조달청(본청·지방청)이 다른 기관을 대신해 체결한 대행 계약인가."""
    ctr = pick(it, "cntrctInsttNm")
    if "조달청" not in ctr:
        return False
    dem = demand_orgs(it)
    return bool(dem) and not any(o in g.ORGS for o in dem)


def corp_names(raw):
    """'[1^주계약업체^단독^업체명^대표^...],[2^...]' → '업체명(주계약), 업체명' 형태로 정리."""
    out = []
    for part in str(raw or "").split("],"):
        f = part.strip("[] ").split("^")
        if len(f) >= 4 and f[3]:
            out.append(f[3])
    return ", ".join(dict.fromkeys(out)) or "-"


def row(svc, it):
    name = pick(it, "bidNtceNm", "cntrctNm", "cnstwkNm", "bfSpecNm", "prdctClsfcNoNm", "bizNm", "cntrctNm")
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
                f"업체 {corp_names(pick(it, 'corpList', 'cntrctCorpNm'))}"]
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
            rows, seen = [], set()
            for it in items:
                org_list, name, no, amt, meta, links = row(svc, it)
                if svc == "계약":
                    if is_proxy_contract(it):
                        continue  # 조달청 대행 계약 제외
                    dem = demand_orgs(it)
                    if dem:
                        org_list = dem
                    # 체결일이 최근 14일 안인 건만(변경계약 등 과거 건·미체결 제외), 중복 제거
                    d = pick(it, "cntrctCnclsDate", "cntrctDate")
                    if not d or d < (datetime.now(g.KST) - timedelta(days=14)).strftime("%Y-%m-%d") \
                            or d > datetime.now(g.KST).strftime("%Y-%m-%d"):
                        continue
                    sig = (name, amt, d)
                    if sig in seen:
                        continue
                    seen.add(sig)
                if keep(org_list, name, kind, amt):
                    tag = g.sism_kind(name)
                    rows.append((amt, org_list, f"[{tag}] {name}" if tag and kind == "용역" else name, no, meta, links))
            rows.sort(key=lambda r: -r[0])
            if svc == "계약" and len(rows) > 40:
                lines.append(f"(참고: {len(rows)}건 중 금액 상위 40건만 표시)")
                rows = rows[:40]
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

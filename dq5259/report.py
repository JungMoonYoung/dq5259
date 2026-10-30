"""FR-05 보고서: 시험성적서 형식의 HTML 보고서와 결함 CSV."""

import csv
import io
import math

from . import ui

ADVICE = {
    "Com-ML-5": "라벨이 없거나 비어 있는 샘플을 재라벨링하거나 학습셋에서 제외",
    "Com-ML-3": "필수 특성이 누락된 레코드를 보완 (5259-4 대체 입력 절차 검토)",
    "Con-ML-1": "중복 원천 파일 제거 — 특정 샘플 과대 반영 방지",
    "Bal-ML-3": "소수 범주 추가 수집 또는 가중치·샘플링으로 보정",
    "Bal-ML-8": "라벨 분포 쏠림 — 목적에 맞는 목표 분포를 정하고 수집 계획 조정",
    "Bal-ML-1": "주간/야간 등 촬영 조건별 수집 비율 점검",
    "Bal-ML-7": "그룹 간 라벨 비율 차이 — 편향 여부 검토 (5259-5 6.6 위험 관리)",
    "Div-ML-3": "기준 미만 범주는 학습이 어려움 — 범주 통합 또는 추가 수집",
    "Idn-ML-1": "직접식별자 삭제·마스킹, 준식별자 범주화(연령대·지역 상위 단위)로 k-익명성 확보",
    "Sim-ML-1": "유사 샘플 군집은 정보량이 낮음 — 대표 샘플만 남기거나 다양한 조건 추가 수집",
    "Con-ML-2": "유사 항목인데 라벨이 다른 쌍을 재검수 — 라벨링 가이드의 판단 기준 보완",
    "Sim-ML-3": "주성분 비율이 낮으면 샘플이 비슷한 장면에 몰려 있음 — 촬영 장소·조건 다양화",
    "Bal-ML-2": "해상도가 섞여 있으면 학습 전 리사이즈 정책을 정하고 원본 해상도를 메타에 기록",
    "Div-ML-1": "라벨 종류 대비 항목 수 비율 — 목적에 필요한 라벨 체계가 충분한지 검토",
}


def fmt(v, digits=4):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        return "∞ (완전 균형)" if math.isinf(v) else f"{v:.{digits}f}"
    return str(v)


def criterion(r):
    th, d = r.get("threshold"), r.get("direction")
    if d == "info" or th is None:
        return "정보 제공"
    return f"≤ {th}" if d == "max" else f"≥ {th}"


def defects_csv(result):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["qm_id", "name", "item", "reason"])
    for r in result["results"]:
        for d in r.get("defects", []):
            reason = d.get("reason", "")
            item = "; ".join(f"{k}={v}" for k, v in d.items() if k != "reason")
            w.writerow([r["qm_id"], r["name"], item, reason])
    for f in result.get("failures", []):
        w.writerow(["READ", "읽기 실패", f"{f['kind']}:{f['file']}", f["reason"]])
    return buf.getvalue().encode("utf-8-sig")  # 엑셀에서 한글이 깨지지 않도록 BOM


def html_report(result):
    e = ui.esc
    ds, p, s = result["dataset"], result["profile"], result["summary"]
    rows = result["results"]
    gate = [r for r in rows if r["stage"] == "gate"]
    evals = [r for r in rows if r["stage"] == "eval"]
    fails = [r for r in rows if r["verdict"] == "FAIL"]

    defect_blocks = []
    for r in rows:
        if not r.get("defects"):
            continue
        keys = list(dict.fromkeys(k for d in r["defects"] for k in d))
        more = (f"<p class='dq-muted'>외 {len(r['defects']) - 10}건은 결함 CSV 참조</p>"
                if len(r["defects"]) > 10 else "")
        defect_blocks.append(
            f"<h4 style='margin:18px 0 6px;color:{ui.COLORS['navy']}'>{e(r['qm_id'])} {e(r['name'])}"
            f" <span class='dq-muted'>· {len(r['defects'])}건</span></h4>"
            + ui.table(keys, [[e(d.get(k, "")) for k in keys] for d in r["defects"][:10]]) + more)

    advice = ui.table(["ID", "측정값", "조치 권고"],
                      [[f"<span class='dq-id'>{e(r['qm_id'])}</span>", e(r["name"]), e(ADVICE.get(r["qm_id"], ""))]
                       for r in fails]) if fails else "<p class='dq-muted'>미충족 항목 없음</p>"
    formulas = ui.table(["ID", "측정값", "근거 조항", "측정 함수 (본 도구 구현)"],
                        [[f"<span class='dq-id'>{e(r['qm_id'])}</span>", e(r["name"]), e(r["clause"]), e(r["formula"])]
                         for r in rows if r["applied"]])
    overview = ui.table(["항목", "내용"], [
        ["데이터셋", e(ds["name"])], ["유형", e(ds["type"])], ["경로", f"<span class='dq-muted'>{e(ds['root'])}</span>"],
        ["라벨 / 원천 파일", f"{p['label_files']} / {p['source_files']}"],
        ["라벨만 / 원천만", f"{p['label_only']} / {p['source_only']}"], ["읽기 실패", p["read_failures"]]])

    gate_banner = (ui.banner("사전 점검 통과 — 데이터가 평가 가능한 상태입니다.", "PASS") if s["gate_passed"]
                   else ui.banner("사전 점검 미통과 — 라벨 누락·중복 등을 먼저 해소해야 본 평가 결과를 신뢰할 수 있습니다.", "FAIL"))

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>데이터 품질 평가 보고서 — {e(ds['name'])}</title>
<style>body{{background:{ui.COLORS['bg']};margin:0}} .wrap{{max-width:1120px;margin:0 auto;padding:28px 18px 48px}}
{ui.CSS}</style></head><body><div class="dq wrap">
{ui.hero("AI 학습데이터 품질 평가 보고서", ds["name"],
         ["ISO/IEC 5259-2 측정값", "ISO/IEC 5259-3 6.3.9 확인 검토", result["tool"], "실행 " + result["run_at"]])}

{ui.section("01  종합 결과", "Summary")}
{ui.kpis(ui.kpi("샘플", f"{p['samples']:,}", f"라벨-원천 쌍 {p['paired']:,}"),
         ui.kpi("사전 점검", "통과" if s["gate_passed"] else "미통과", f"{len(gate)}개 측정값"),
         ui.kpi("본 평가 충족", f"{s['eval_passed']} / {s['eval_judged']}", "판정 대상 측정값"),
         ui.score_kpi("충족률", s["eval_score"], "본 평가 기준"))}
{gate_banner}

{ui.section("02  사전 점검", "일반 데이터 품질 · 평가 가능 여부 확인")}
{ui.cards(gate)}

{ui.section("03  본 평가", "ML 전용 데이터 품질 · ISO/IEC 5259-2 6.5")}
{ui.cards(evals)}
<p class="dq-muted">기준값은 예시이며 사용 목적에 따라 조정해야 한다 (5259-3 6.3.10 b). '정보' 항목은 목적별 기준이 달라 판정하지 않는다.</p>

{ui.section("04  조치 권고", "미충족 항목")}
{advice}

{ui.section("05  결함 상세", "측정값별 상위 10건")}
{''.join(defect_blocks) or "<p class='dq-muted'>결함 없음</p>"}

{ui.section("06  데이터셋 개요", "Profile")}
{overview}

{ui.section("07  측정 함수", "근거 조항과 구현")}
{formulas}
<p class="dq-muted">5259-2가 ISO/IEC 25024를 참조만 하는 측정값은 사용하지 않았다. Sim-ML-1은 비고 7에 따라 X = 1 − B/A로 해석했다.</p>
</div></body></html>"""

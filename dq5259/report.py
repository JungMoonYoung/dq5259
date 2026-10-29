"""FR-05 보고서: 시험성적서 형식의 HTML 보고서와 결함 CSV."""

import csv
import html
import io
import math

VERDICT_COLOR = {"PASS": "#1a7f37", "FAIL": "#cf222e", "INFO": "#0969da", "N/A": "#6e7781", "미적용": "#6e7781"}

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


def _table(headers, rows):
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _badge(v):
    return f'<span class="badge" style="background:{VERDICT_COLOR.get(v, "#6e7781")}">{html.escape(v)}</span>'


def html_report(result):
    e = html.escape
    ds, p, s = result["dataset"], result["profile"], result["summary"]
    rows = result["results"]

    def qm_rows(stage):
        return [[e(r["qm_id"]), e(r["name"]), e(r["characteristic"]), e(r["clause"]),
                 "적용" if r["applied"] else "미적용",
                 fmt(r["A"], 2), fmt(r["B"], 2), fmt(r["value"]), criterion(r), _badge(r["verdict"]),
                 e(r.get("note") or "")]
                for r in rows if r["stage"] == stage]

    hdr = ["ID", "측정값", "품질 특성", "근거", "적용", "A", "B", "X", "기준", "판정", "비고"]
    defect_blocks = []
    for r in rows:
        if not r.get("defects"):
            continue
        keys = list(dict.fromkeys(k for d in r["defects"] for k in d))
        sample = r["defects"][:10]
        more = f"<p class='muted'>외 {len(r['defects']) - 10}건 (CSV 참조)</p>" if len(r["defects"]) > 10 else ""
        defect_blocks.append(f"<h3>{e(r['qm_id'])} {e(r['name'])} — {len(r['defects'])}건</h3>"
                             + _table(keys, [[e(str(d.get(k, ''))) for k in keys] for d in sample]) + more)

    advice = [[e(r["qm_id"]), e(r["name"]), e(ADVICE.get(r["qm_id"], ""))]
              for r in rows if r["verdict"] == "FAIL"]
    formulas = [[e(r["qm_id"]), e(r["formula"])] for r in rows if r["applied"]]
    gate_txt = "통과" if s["gate_passed"] else "미통과 — 본 평가 결과의 신뢰도가 제한됨"
    score = "-" if s["eval_score"] is None else f"{s['eval_score']}%"

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>데이터 품질 평가 보고서 — {e(ds['name'])}</title>
<style>
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:1100px;margin:32px auto;padding:0 16px;color:#1f2328}}
h1{{border-bottom:3px solid #0b2e59;padding-bottom:8px;color:#0b2e59}} h2{{color:#0b2e59;margin-top:32px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}}
th,td{{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}} th{{background:#f0f4f8}}
.badge{{color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:bold}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap}} .kpi div{{border:1px solid #d0d7de;border-radius:8px;padding:10px 16px;min-width:140px}}
.kpi b{{display:block;font-size:22px;color:#0b2e59}} .muted{{color:#6e7781;font-size:12px}}
</style></head><body>
<h1>AI 학습데이터 품질 평가 보고서</h1>
<p class="muted">{e(result['tool'])} · 실행 {e(result['run_at'])} · 근거: ISO/IEC 5259-2 (측정값), ISO/IEC 5259-3 6.3.9 (확인 검토 절차)</p>

<h2>1. 데이터셋 개요</h2>
{_table(["항목", "내용"], [["데이터셋", e(ds['name'])], ["유형", e(ds['type'])], ["경로", e(str(ds['root']))],
                          ["샘플 수", p['samples']], ["라벨/원천 파일", f"{p['label_files']} / {p['source_files']}"],
                          ["라벨-원천 쌍", p['paired']], ["읽기 실패", p['read_failures']]])}

<h2>2. 종합 결과</h2>
<div class="kpi"><div>사전 점검<b>{e(gate_txt.split(' ')[0])}</b></div>
<div>본 평가 판정 항목<b>{s['eval_judged']}</b></div><div>PASS<b>{s['eval_passed']}</b></div><div>충족률<b>{score}</b></div></div>
<p>사전 점검: {e(gate_txt)}</p>

<h2>3. 사전 점검 (일반 데이터 품질)</h2>
{_table(hdr, qm_rows('gate'))}

<h2>4. 본 평가 (ML 전용 데이터 품질)</h2>
{_table(hdr, qm_rows('eval'))}
<p class="muted">기준값은 예시이며 사용 목적에 따라 조정해야 한다 (5259-3 6.3.9 b). '정보 제공' 항목은 목적별 기준이 달라 판정하지 않는다.</p>

<h2>5. 결함 상세</h2>
{''.join(defect_blocks) or '<p>결함 없음</p>'}

<h2>6. 조치 권고</h2>
{_table(["ID", "측정값", "권고"], advice) if advice else '<p>FAIL 항목 없음</p>'}

<h2>7. 측정 함수</h2>
{_table(["ID", "측정 함수 (본 도구 구현)"], formulas)}
<p class="muted">5259-2가 ISO/IEC 25024를 참조만 하는 측정값은 사용하지 않았다. Sim-ML-1은 비고 7에 따라 X = 1 − B/A로 해석했다.</p>
</body></html>"""

"""사전 점검(게이트): 본 평가 전에 데이터가 평가 가능한 상태인지 확인한다.

범용 진단 도구가 다루는 영역이므로 최소한으로만 둔다.
"""

from collections import defaultdict

from .. import jsonpath
from . import QMResult, not_applicable, ratio, register


@register("Com-ML-5", "라벨 완전성", "완전성", "5259-2 6.2.2.2 표 2",
          "X = A/B  (A: 라벨이 없거나 불완전한 샘플 수, B: 전체 샘플 수)", stage="gate")
def label_completeness(prof, cfg, params):
    empty_path = cfg["fields"]["empty_check"]
    labels_only = cfg["dataset"].get("labels_only", False)
    defects = []
    for s in prof.samples:
        if s.label_path is None:
            reason = "원천만 있고 라벨 파일 없음"
        elif s.label is None:
            reason = f"라벨 읽기 실패: {s.label_error}"
        elif s.source_path is None and not labels_only:
            reason = "라벨만 있고 원천 파일 없음"
        elif empty_path and all(jsonpath.is_null(v) for v in jsonpath.get(s.label, empty_path)):
            reason = f"'{empty_path}' 비어 있음"
        else:
            continue
        defects.append({"sample": s.key, "reason": reason})
    A, B = len(defects), len(prof.samples)
    note = "라벨 전용 평가 — 원천 누락은 결함으로 보지 않음" if labels_only else ""
    return QMResult("Com-ML-5", A, B, ratio(A, B), defects, note=note)


@register("Com-ML-3", "특성 완전성", "완전성", "5259-2 6.2.2.2 표 2",
          "X = A/B  (특성별 — A: null 아닌 항목 수, B: 해당 특성 전체 항목 수). 최솟값 특성으로 판정",
          stage="gate")
def feature_completeness(prof, cfg, params):
    paths = cfg["fields"]["required"]
    if not paths:
        return not_applicable("Com-ML-3", "필수 특성(fields.required)이 지정되지 않음")
    counts = defaultdict(lambda: [0, 0])
    defects = []
    for s in prof.labeled:
        for p in paths:
            for v in jsonpath.get(s.label, p):
                counts[p][1] += 1
                if jsonpath.is_null(v):
                    defects.append({"sample": s.key, "field": p, "reason": "null 또는 누락"})
                else:
                    counts[p][0] += 1
    per_feature = {p: {"A": a, "B": b, "X": ratio(a, b)} for p, (a, b) in counts.items()}
    if not per_feature:
        return not_applicable("Com-ML-3", "라벨을 읽을 수 있는 샘플이 없음")
    worst = min(per_feature, key=lambda p: per_feature[p]["X"] if per_feature[p]["X"] is not None else 1)
    w = per_feature[worst]
    return QMResult("Com-ML-3", w["A"], w["B"], w["X"], defects,
                    detail={"per_feature": per_feature, "worst": worst},
                    note=f"가장 낮은 특성: {worst}")


@register("Con-ML-1", "데이터 레코드 일관성", "일관성", "5259-2 6.2.3.2 표 3",
          "X = A/B  (A: 중복 레코드 수, B: 전체 레코드 수)", stage="gate")
def record_duplicates(prof, cfg, params):
    groups = defaultdict(list)
    for s in prof.samples:
        if s.source_hash:
            groups[s.source_hash].append(s.key)
    defects = []
    for keys in groups.values():
        for dup in keys[1:]:  # 첫 번째는 원본, 나머지를 중복으로 본다
            defects.append({"sample": dup, "reason": f"원천 파일이 '{keys[0]}'와 동일 (SHA-1)"})
    A, B = len(defects), sum(len(k) for k in groups.values())
    return QMResult("Con-ML-1", A, B, ratio(A, B), defects)

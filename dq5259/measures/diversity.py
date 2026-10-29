"""다양성(Diversity) — 5259-2 6.5.3.2 표 17."""

from . import QMResult, not_applicable, register
from .balance import category_counts


@register("Div-ML-3", "범주 크기 다양성", "다양성", "5259-2 6.5.3.2 표 17",
          "X = A/B  (A: 항목 수가 기준 미만인 범주 수, B: 전체 범주 수)")
def category_size_diversity(prof, cfg, params):
    if not cfg["fields"]["categories"]:
        return not_applicable("Div-ML-3", "범주 라벨 경로(fields.categories)가 지정되지 않음")
    c = category_counts(prof, cfg)
    if not c:
        return not_applicable("Div-ML-3", "범주 라벨이 없음")
    min_count = params.get("min_count", 10)
    small = {k: v for k, v in c.items() if v < min_count}
    A, B = len(small), len(c)
    return QMResult("Div-ML-3", A, B, A / B,
                    defects=[{"category": k, "count": v, "reason": f"항목 수 {v} < 기준 {min_count}"}
                             for k, v in sorted(small.items(), key=lambda kv: kv[1])],
                    detail={"counts": dict(c.most_common()), "min_count": min_count},
                    note=f"범주 최소 항목 수 기준: {min_count} (품질 요구사항으로 조정)")

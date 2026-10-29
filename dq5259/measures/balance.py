"""균형(Balance) — 5259-2 6.5.2.2 표 16."""

import math
from collections import Counter, defaultdict

from .. import jsonpath
from . import QMResult, not_applicable, ratio, register

CLAUSE = "5259-2 6.5.2.2 표 16"


def category_counts(prof, cfg):
    path = cfg["fields"]["categories"]
    c = Counter()
    for s in prof.labeled:
        for v in jsonpath.get(s.label, path):
            if not jsonpath.is_null(v):
                c[str(v)] += 1
    return c


def inverse_max_deviation(values):
    """'평균 대비 최대 절대편차 비율의 역수' = A/B (A: 평균, B: 최대 절대편차).

    값이 클수록 균형. 모든 값이 같으면(B=0) 완전 균형이므로 무한대로 둔다.
    """
    A = sum(values) / len(values)
    B = max(abs(v - A) for v in values)
    return A, B, (A / B if B else math.inf)


@register("Bal-ML-3", "범주 간 균형", "균형", CLAUSE,
          "X = A/B  (A: 평균 범주 크기, B: 범주 크기와 A의 최대 절대 차이)")
def category_balance(prof, cfg, params):
    if not cfg["fields"]["categories"]:
        return not_applicable("Bal-ML-3", "범주 라벨 경로(fields.categories)가 지정되지 않음")
    c = category_counts(prof, cfg)
    if len(c) < 2:
        return not_applicable("Bal-ML-3", "범주가 2개 미만이라 균형을 정의할 수 없음")
    A, B, X = inverse_max_deviation(list(c.values()))
    far = max(c, key=lambda k: abs(c[k] - A))
    return QMResult("Bal-ML-3", A, B, X,
                    defects=[{"category": far, "count": c[far], "reason": f"평균({A:.1f})에서 가장 멀리 떨어진 범주"}],
                    detail={"counts": dict(c.most_common())})


def js_divergence(p, q):
    """Jensen-Shannon Divergence (밑 2, 0~1)."""
    m = [(a + b) / 2 for a, b in zip(p, q)]

    def kl(x, y):
        return sum(a * math.log2(a / b) for a, b in zip(x, y) if a > 0)

    return (kl(p, m) + kl(q, m)) / 2


@register("Bal-ML-8", "라벨 분포 균형", "균형", CLAUSE,
          "X = f(A, B)  (A: 실제 라벨 분포, B: 균일 분포, f: Jensen-Shannon Divergence)")
def label_distribution(prof, cfg, params):
    if not cfg["fields"]["categories"]:
        return not_applicable("Bal-ML-8", "범주 라벨 경로(fields.categories)가 지정되지 않음")
    c = category_counts(prof, cfg)
    if len(c) < 2:
        return not_applicable("Bal-ML-8", "범주가 2개 미만")
    n, N = sum(c.values()), len(c)
    actual = [v / n for v in c.values()]
    uniform = [1 / N] * N
    X = js_divergence(actual, uniform)
    return QMResult("Bal-ML-8", None, None, X,
                    detail={"distribution": {k: v / n for k, v in c.items()}},
                    note=f"범주 {N}개, 항목 {n}개. 0이면 완전 균일, 1에 가까울수록 쏠림")


@register("Bal-ML-1", "밝기 균형", "균형", CLAUSE,
          "X = A/B  (A: 평균 밝기, B: 각 이미지 밝기와 A의 최대 절대 차이)", data_types=("image",))
def brightness_balance(prof, cfg, params):
    items = [(s.key, s.source_meta["brightness"]) for s in prof.samples
             if s.source_meta and "brightness" in s.source_meta]
    if len(items) < 2:
        return not_applicable("Bal-ML-1", "밝기를 읽을 수 있는 이미지가 2장 미만")
    A, B, X = inverse_max_deviation([b for _, b in items])
    ranked = sorted(items, key=lambda kv: abs(kv[1] - A), reverse=True)[:10]
    return QMResult("Bal-ML-1", A, B, X,
                    defects=[{"sample": k, "brightness": round(b, 1),
                              "reason": f"평균 밝기({A:.1f})와 차이 {abs(b - A):.1f}"} for k, b in ranked],
                    detail={"brightness": [b for _, b in items]})


def resolve_group(root, item, expr):
    """unit_group 식 해석. '^info.time' → 루트 기준, '^{SpeakerNo}.Gender' → 항목 값으로 키 치환."""
    if expr.startswith("^"):
        expr = expr[1:]
        base = root
    else:
        base = item
    if "{" in expr:
        start, end = expr.index("{"), expr.index("}")
        key = item.get(expr[start + 1:end]) if isinstance(item, dict) else None
        if key is None:
            return None
        expr = expr[:start] + str(key) + expr[end + 1:]
    vals = jsonpath.get(base, expr)
    v = vals[0] if vals else jsonpath.MISSING
    return None if jsonpath.is_null(v) else str(v)


@register("Bal-ML-7", "라벨 비율 균형", "균형", CLAUSE,
          "X = |A - B|  (A·B: 두 범주 그룹에서 라벨 L을 갖는 항목 비율). 모든 L·그룹 쌍 중 최댓값")
def label_ratio_balance(prof, cfg, params):
    f = cfg["fields"]
    if not (f["unit_items"] and f["unit_label"] and f["unit_group"]):
        return not_applicable("Bal-ML-7", "그룹 비교 설정(unit_items/unit_label/unit_group)이 없음")
    table = defaultdict(Counter)  # group -> label -> count
    for s in prof.labeled:
        for item in jsonpath.get(s.label, f["unit_items"]):
            if not isinstance(item, dict):
                continue
            lab = jsonpath.get(item, f["unit_label"])[0]
            grp = resolve_group(s.label, item, f["unit_group"])
            if grp is None or jsonpath.is_null(lab):
                continue
            table[grp][str(lab)] += 1
    groups = sorted(table)
    if len(groups) < 2:
        return not_applicable("Bal-ML-7", "비교할 그룹이 2개 미만")
    labels = sorted({l for g in groups for l in table[g]})
    totals = {g: sum(table[g].values()) for g in groups}
    best = None
    for L in labels:
        rates = {g: table[g][L] / totals[g] for g in groups}
        hi, lo = max(rates, key=rates.get), min(rates, key=rates.get)
        gap = rates[hi] - rates[lo]
        if best is None or gap > best[0]:
            best = (gap, L, hi, rates[hi], lo, rates[lo])
    gap, L, hi, a, lo, b = best
    return QMResult("Bal-ML-7", a, b, gap,
                    defects=[{"label": L, "group_high": hi, "rate_high": round(a, 3),
                              "group_low": lo, "rate_low": round(b, 3),
                              "reason": f"라벨 '{L}' 비율이 그룹 간 {gap:.1%}p 차이"}],
                    detail={"table": {g: dict(table[g]) for g in groups}, "group_field": f["unit_group"]},
                    note=f"그룹 기준: {f['unit_group']}")


@register("Bal-ML-2", "해상도 균형", "균형", CLAUSE,
          "X = A/B  (A: 평균 해상도(픽셀 수), B: 각 이미지 해상도와 A의 최대 절대 차이)", data_types=("image",))
def resolution_balance(prof, cfg, params):
    items = [(s.key, s.source_meta["width"], s.source_meta["height"]) for s in prof.samples
             if s.source_meta and "width" in s.source_meta]
    if len(items) < 2:
        return not_applicable("Bal-ML-2", "해상도를 읽을 수 있는 이미지가 2장 미만")
    A, B, X = inverse_max_deviation([w * h for _, w, h in items])
    sizes = Counter(f"{w}×{h}" for _, w, h in items)
    far = max(items, key=lambda it: abs(it[1] * it[2] - A))
    defects = [] if B == 0 else [{"sample": far[0], "resolution": f"{far[1]}×{far[2]}",
                                  "reason": f"평균 {A:,.0f}px에서 가장 먼 해상도"}]
    return QMResult("Bal-ML-2", A, B, X, defects, detail={"resolutions": dict(sizes.most_common())},
                    note="해상도 종류: " + ", ".join(f"{k} {v}장" for k, v in sizes.most_common(4)))

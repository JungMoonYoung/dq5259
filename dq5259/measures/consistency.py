"""데이터 라벨 일관성 — 5259-2 6.2.3.2 표 3 (Con-ML-2).

X = A/B
  A: 동일한 라벨이 지정된 유사한 항목 쌍의 수
  B: 유사한 항목 라벨 간에 수행된 총 비교 횟수

'유사한 항목'의 판단 (표준은 방법을 정하지 않으므로 데이터 유형별로 정의)
  - 단위 항목 모드: fields.similar_key 값이 같은 항목 (예: 같은 문장의 발화)
  - 이미지 모드: dHash 해밍 거리 ≤ h 인 이미지 쌍, 라벨은 이미지의 범주 집합
"""

from collections import Counter, defaultdict
from math import comb

from .. import jsonpath
from . import QMResult, not_applicable, register


def _unit_mode(prof, cfg):
    f = cfg["fields"]
    groups = defaultdict(list)  # 정규화한 키 -> [(샘플, 라벨)]
    for s in prof.labeled:
        for item in jsonpath.get(s.label, f["unit_items"]):
            if not isinstance(item, dict):
                continue
            key = jsonpath.get(item, f["similar_key"])[0]
            lab = jsonpath.get(item, f["unit_label"])[0]
            if jsonpath.is_null(key) or jsonpath.is_null(lab):
                continue
            groups[" ".join(str(key).split())].append((s.key, str(lab)))
    A = B = 0
    defects = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        labels = Counter(lab for _, lab in items)
        pairs, same = comb(len(items), 2), sum(comb(k, 2) for k in labels.values())
        A, B = A + same, B + pairs
        if same < pairs:
            defects.append({"key": key[:40], "items": len(items), "labels": dict(labels),
                            "samples": ", ".join(dict.fromkeys(k for k, _ in items))[:80],
                            "reason": f"같은 '{f['similar_key']}' {len(items)}건에 라벨 {len(labels)}종"})
    return A, B, defects, f"유사 기준: '{f['similar_key']}' 값이 같은 항목"


def _image_mode(prof, cfg, h):
    path = cfg["fields"]["categories"]
    items = []
    for s in prof.labeled:
        if s.source_meta and "dhash" in s.source_meta:
            cats = frozenset(str(v) for v in jsonpath.get(s.label, path) if not jsonpath.is_null(v))
            items.append((s.key, s.source_meta["dhash"], cats))
    A = B = 0
    defects = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if bin(items[i][1] ^ items[j][1]).count("1") > h:
                continue
            B += 1
            if items[i][2] == items[j][2]:
                A += 1
            else:
                only_a, only_b = items[i][2] - items[j][2], items[j][2] - items[i][2]
                defects.append({"sample_a": items[i][0], "sample_b": items[j][0],
                                "only_a": ", ".join(sorted(only_a)) or "-", "only_b": ", ".join(sorted(only_b)) or "-",
                                "reason": "유사 이미지인데 범주 구성이 다름"})
    return A, B, defects, f"유사 기준: dHash 해밍 거리 ≤ {h}, 라벨 = 이미지의 범주 집합"


@register("Con-ML-2", "데이터 라벨 일관성", "일관성", "5259-2 6.2.3.2 표 3",
          "X = A/B  (A: 동일 라벨이 지정된 유사 항목 쌍 수, B: 유사 항목 라벨 비교 총 횟수)")
def label_consistency(prof, cfg, params):
    f = cfg["fields"]
    if f["similar_key"] and f["unit_items"] and f["unit_label"]:
        A, B, defects, note = _unit_mode(prof, cfg)
    elif cfg["dataset"]["type"] == "image" and f["categories"]:
        A, B, defects, note = _image_mode(prof, cfg, params.get("hamming", 6))
    else:
        return not_applicable("Con-ML-2", "유사 판단 기준이 없음 (fields.similar_key 또는 이미지 범주)")
    if B == 0:
        return not_applicable("Con-ML-2", "비교할 유사 항목 쌍이 없음")
    return QMResult("Con-ML-2", A, B, A / B, defects, note=note)

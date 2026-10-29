"""식별가능성(Identifiability) — 5259-2 6.5.5.2 표 19.

A: 단독으로 또는 다른 데이터 항목과 결합하여 식별에 활용될 수 있는 항목을 포함한 레코드 수
B: 전체 레코드 수

- '단독으로'  → 직접식별자 패턴 (개인정보 13종)
- '결합하여' → 준식별자 조합이 k명 미만인 레코드 (k-익명성 위반)
"""

import re
from collections import Counter

from .. import jsonpath
from . import QMResult, register

# GS 시험(생성형 AI 개인정보 유출 방지 SW)에서 정의했던 개인정보 패턴을 정규식으로 옮김
PII_PATTERNS = {
    "주민등록번호": r"\b\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-?[1-4]\d{6}\b",
    "외국인등록번호": r"\b\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-?[5-8]\d{6}\b",
    "여권번호": r"\b[MSRODG]\d{8}\b",
    "운전면허번호": r"\b\d{2}-\d{2}-\d{6}-\d{2}\b",
    "카드번호": r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",
    "계좌번호": r"\b\d{3,6}-\d{2,6}-\d{4,8}\b",
    "건강보험번호": r"\b\d{10}-?\d\b",
    "휴대전화": r"\b01[016789]-?\d{3,4}-?\d{4}\b",
    "일반전화": r"\b0(2|[3-6][1-5])-\d{3,4}-\d{4}\b",
    "이메일": r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
    "법인등록번호": r"\b\d{6}-\d{7}\b",
    "사업자등록번호": r"\b\d{3}-\d{2}-\d{5}\b",
}
# 이름은 패턴만으로 오탐이 많아 '이름/성명' 류 키에 값이 있는 경우만 본다
NAME_KEYS = re.compile(r"(^|[._])(name|성명|이름|fullname)$", re.I)
COMPILED = {k: re.compile(v) for k, v in PII_PATTERNS.items()}
# 숫자 ID·좌표 등 오탐 방지를 위해 검사에서 제외할 키
SKIP_KEYS = re.compile(r"(id|_id|date|time|length|gps|pose|parameter|mask|filename|file_name)$", re.I)


def mask(text):
    return text[:2] + "*" * max(0, len(text) - 4) + text[-2:] if len(text) > 4 else "****"


def direct_identifiers(label):
    hits = []
    for path, value in jsonpath.iter_strings(label):
        leaf = re.sub(r"\[\d+\]", "", path).split(".")[-1]
        if NAME_KEYS.search(leaf) and value.strip():
            hits.append(("이름", path, value))
            continue
        if SKIP_KEYS.search(leaf):
            continue
        for kind, rx in COMPILED.items():
            m = rx.search(value)
            if m:
                hits.append((kind, path, m.group(0)))
                break
    return hits


@register("Idn-ML-1", "식별가능성 비율", "식별가능성", "5259-2 6.5.5.2 표 19",
          "X = A/B  (A: 단독 또는 결합으로 식별에 활용될 수 있는 레코드 수, B: 전체 레코드 수)")
def identifiability(prof, cfg, params):
    f = cfg["fields"]
    k = params.get("k", 5)
    qi = f["quasi_identifiers"]
    flagged = {}

    # 1) 단독 식별: 직접식별자 (라벨 값 + 파일명)
    for s in prof.samples:
        texts = []
        if s.label is not None:
            texts += direct_identifiers(s.label)
        for kind, rx in COMPILED.items():
            m = rx.search(s.key)
            if m:
                texts.append((kind, "(파일명)", m.group(0)))
        if texts:
            kind, path, val = texts[0]
            flagged[s.key] = {"sample": s.key, "type": "직접식별자", "kind": kind,
                              "field": path, "value": mask(val), "reason": f"{kind} 패턴 검출"}

    # 2) 결합 식별: 준식별자 조합의 등가 클래스 크기 < k
    persons = []
    if qi and f["person_items"]:
        for s in prof.labeled:
            for p in f["person_items"]:
                for person in jsonpath.get(s.label, p):
                    if isinstance(person, dict):
                        combo = tuple(str(person.get(q, "")) for q in qi)
                        persons.append((s.key, combo))
        sizes = Counter(c for _, c in persons)
        for key, combo in persons:
            if sizes[combo] < k and key not in flagged:
                flagged[key] = {"sample": key, "type": "준식별자 결합", "kind": "k-익명성 위반",
                                "field": "+".join(qi), "value": " / ".join(combo),
                                "reason": f"동일 조합 {sizes[combo]}명 (< k={k})"}
    else:
        sizes = Counter()

    A, B = len(flagged), len(prof.samples)
    note = f"직접식별자 13종 패턴 + 준식별자({', '.join(qi) or '없음'}) k={k}"
    return QMResult("Idn-ML-1", A, B, A / B if B else None, list(flagged.values()),
                    detail={"direct": sum(1 for d in flagged.values() if d["type"] == "직접식별자"),
                            "quasi": sum(1 for d in flagged.values() if d["type"] == "준식별자 결합"),
                            "equivalence_classes": len(sizes)},
                    note=note)

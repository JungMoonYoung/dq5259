"""측정값 레지스트리 (NFR-06: QM을 함수 하나로 추가).

각 측정값은 ISO/IEC 5259-2의 측정 함수(X = A/B 등)를 그대로 따르고,
A·B·X와 결함 위치를 함께 돌려준다 (FR-04-2, FR-04-3).
"""

from dataclasses import dataclass, field

REGISTRY = {}


@dataclass
class QMSpec:
    qm_id: str
    name: str
    characteristic: str
    clause: str
    formula: str
    stage: str            # gate | eval
    data_types: tuple     # ("image", "audio")
    func: object = None


@dataclass
class QMResult:
    qm_id: str
    A: float | None
    B: float | None
    value: float | None
    defects: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)   # 차트·설명용 부가 정보
    note: str = ""
    applicable: bool = True


def register(qm_id, name, characteristic, clause, formula, stage="eval", data_types=("image", "audio")):
    def deco(func):
        REGISTRY[qm_id] = QMSpec(qm_id, name, characteristic, clause, formula, stage, data_types, func)
        return func
    return deco


def not_applicable(qm_id, reason):
    return QMResult(qm_id, None, None, None, note=reason, applicable=False)


def ratio(a, b):
    return a / b if b else None


# 등록을 위해 모듈을 불러온다
from . import gate, balance, diversity, identifiability, similarity  # noqa: E402,F401

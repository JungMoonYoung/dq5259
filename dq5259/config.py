"""진단 설정(YAML). 5259-3 6.3.9 b의 '기준값 문서화'를 파일로 남기는 역할도 한다."""

import copy
from pathlib import Path

import yaml

# 측정값별 기본 기준값과 판정 방향.
#   max  : 값이 기준 이하이면 PASS (결함 비율류)
#   min  : 값이 기준 이상이면 PASS (균형·완전성류)
#   info : 판정하지 않고 정보만 제공
DEFAULT_MEASURES = {
    "Com-ML-5": {"enabled": True, "threshold": 0.01, "direction": "max"},
    "Com-ML-3": {"enabled": True, "threshold": 0.99, "direction": "min"},
    "Con-ML-1": {"enabled": True, "threshold": 0.01, "direction": "max"},
    "Bal-ML-3": {"enabled": True, "threshold": 0.5, "direction": "min"},
    "Bal-ML-8": {"enabled": True, "threshold": 0.3, "direction": "max"},
    # 밝기 분포는 촬영 목적(주간 전용/주야간 혼합)에 따라 기준이 달라 정보 제공으로 둔다
    "Bal-ML-1": {"enabled": True, "threshold": None, "direction": "info"},
    "Bal-ML-7": {"enabled": True, "threshold": 0.1, "direction": "max"},
    "Div-ML-3": {"enabled": True, "threshold": 0.2, "direction": "max", "min_count": 10},
    "Idn-ML-1": {"enabled": True, "threshold": 0.0, "direction": "max", "k": 5},
    "Sim-ML-1": {"enabled": True, "threshold": None, "direction": "info", "hamming": 6},
}

DEFAULT_CONFIG = {
    "dataset": {
        "name": "unnamed",
        "type": "image",          # image | audio
        "root": ".",
        "label_ext": [".json", ".jsonl"],
        "source_ext": [".jpg", ".jpeg", ".png"],
        "label_suffix": "",       # 라벨 파일명 끝의 접미사 (예: _label) — 쌍 매칭 시 제거
    },
    "fields": {
        "empty_check": None,      # 비어 있으면 '불완전 라벨'로 보는 경로
        "categories": None,       # 객체(또는 레코드) 단위 범주 라벨 경로
        "required": [],           # Com-ML-3 대상 특성 경로
        "unit_items": None,       # Bal-ML-7 단위 항목 경로 (예: annotation[])
        "unit_label": None,       # 단위 항목 내 라벨 (상대 경로)
        "unit_group": None,       # 그룹 속성 (^로 시작하면 루트 기준, {필드}는 항목 값으로 치환)
        "person_items": [],       # 사람 정보 객체 경로 목록
        "quasi_identifiers": [],  # 준식별자 필드
    },
    "measures": DEFAULT_MEASURES,
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path_or_dict):
    if isinstance(path_or_dict, dict):
        user = path_or_dict
        base_dir = Path(".")
    else:
        p = Path(path_or_dict)
        user = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        base_dir = p.parent
    cfg = _merge(DEFAULT_CONFIG, user)
    root = Path(cfg["dataset"]["root"])
    if not root.is_absolute():
        root = (base_dir / root).resolve()
    cfg["dataset"]["root"] = str(root)
    return cfg


def dump(cfg, path):
    Path(path).write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

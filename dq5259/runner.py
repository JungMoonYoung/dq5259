"""진단 실행 파이프라인.

5259-3 조항과의 대응
  측정값 식별 (6.3.10 c)          → select()     : 데이터 유형에 맞는 QM 추천 + 설정의 enabled
  기준값 문서화 (6.3.10 b)        → cfg.measures : threshold/direction (YAML로 저장)
  측정값으로 품질 확인 (6.3.9)    → run()        : 각 QM 함수 실행·판정
  측정값·기준값 기록 (6.4 d, e)   → save_run()   : 설정·결과를 JSON으로 보관
"""

import json
import math
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import __version__, profile
from .measures import REGISTRY


def select(cfg):
    """(QM ID, 적용 여부, 미적용 사유) 목록."""
    dtype = cfg["dataset"]["type"]
    out = []
    for qm_id, spec in REGISTRY.items():
        m = cfg["measures"].get(qm_id, {})
        if dtype not in spec.data_types:
            out.append((qm_id, False, f"{dtype} 데이터에 해당하지 않는 측정값"))
        elif not m.get("enabled", True):
            out.append((qm_id, False, m.get("reason") or "사용자가 미적용으로 설정"))
        else:
            out.append((qm_id, True, ""))
    return out


def judge(value, m):
    direction = m.get("direction", "info")
    th = m.get("threshold")
    if value is None:
        return "N/A"
    if direction == "info" or th is None:
        return "INFO"
    ok = value <= th if direction == "max" else value >= th
    return "PASS" if ok else "FAIL"


def run(cfg, progress=None):
    prof = profile.build(cfg, progress)
    rows = []
    for qm_id, applied, reason in select(cfg):
        spec = REGISTRY[qm_id]
        m = cfg["measures"].get(qm_id, {})
        base = {"qm_id": qm_id, "name": spec.name, "characteristic": spec.characteristic,
                "clause": spec.clause, "formula": spec.formula, "stage": spec.stage,
                "threshold": m.get("threshold"), "direction": m.get("direction", "info")}
        if not applied:
            rows.append({**base, "applied": False, "verdict": "미적용", "note": reason,
                         "A": None, "B": None, "value": None, "defects": [], "detail": {}})
            continue
        res = spec.func(prof, cfg, m)
        verdict = judge(res.value, m) if res.applicable else "미적용"
        rows.append({**base, **asdict(res), "applied": res.applicable, "verdict": verdict})

    gate = [r for r in rows if r["stage"] == "gate" and r["applied"]]
    gate_ok = all(r["verdict"] != "FAIL" for r in gate)
    judged = [r for r in rows if r["stage"] == "eval" and r["verdict"] in ("PASS", "FAIL")]
    passed = sum(r["verdict"] == "PASS" for r in judged)
    return {
        "tool": f"DQ-5259 {__version__}",
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": cfg["dataset"],
        "config": cfg,
        "profile": prof.summary(),
        "failures": prof.failures,
        "results": rows,
        "summary": {
            "gate_passed": gate_ok,
            "eval_judged": len(judged),
            "eval_passed": passed,
            "eval_score": round(100 * passed / len(judged), 2) if judged else None,
        },
    }


def _jsonable(o):
    if isinstance(o, float) and math.isinf(o):
        return "inf"
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, Path):
        return str(o)
    return o


def save_run(result, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = result["run_at"].replace(":", "").replace("-", "")
    path = out / f"run_{stamp}.json"
    path.write_text(json.dumps(_jsonable(result), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_runs(out_dir):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(out_dir).glob("run_*.json"))]

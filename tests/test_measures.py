"""SRS 8장 인수 기준 (AT-01 ~ AT-05)."""

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from dq5259 import config, runner
from dq5259.measures.balance import inverse_max_deviation, js_divergence
from dq5259.measures.similarity import pca_components

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


@pytest.fixture(scope="session", autouse=True)
def synthetic():
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_synthetic.py")], check=True, capture_output=True)


def run(name):
    cfg = config.load(ROOT / "configs" / f"synthetic_{name}.yaml")
    res = runner.run(cfg)
    exp = json.loads((SAMPLES / f"{name}_expected.json").read_text(encoding="utf-8"))
    return {r["qm_id"]: r for r in res["results"]}, res, exp


# ---------- 측정 함수 단위 검증 (손계산 값과 비교) ----------

def test_inverse_max_deviation():
    A, B, X = inverse_max_deviation([10, 20, 30])  # 평균 20, 최대편차 10
    assert (A, B, X) == (20, 10, 2)
    assert inverse_max_deviation([5, 5])[2] == math.inf  # 완전 균형


def test_js_divergence():
    assert js_divergence([0.5, 0.5], [0.5, 0.5]) == 0
    assert js_divergence([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)  # 밑 2 → 최대 1


def test_pca_components():
    # 모든 샘플이 한 방향(1차원)에만 퍼져 있으면 주성분 1개로 설명된다
    line = [[t, 2 * t, 3 * t, 4 * t] for t in range(1, 8)]
    assert pca_components(line) == 1
    # 서로 직교하는 4개 방향에 고르게 퍼져 있으면 정규화 후에도 여러 성분이 필요하다
    spread = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [-1, 0, 0, 0], [0, -1, 0, 0]]
    assert pca_components(spread) >= 3


# ---------- AT-01 결함 주입 데이터: 심은 결함 수와 측정 결과 일치 ----------

def test_at01_robot():
    r, res, exp = run("robot")
    assert res["profile"]["samples"] == exp["samples"]
    assert r["Com-ML-5"]["A"] == exp["com_ml_5"]
    assert r["Con-ML-1"]["A"] == exp["con_ml_1"]
    assert res["profile"]["read_failures"] == exp["read_failures"]
    weather_nulls = [d for d in r["Com-ML-3"]["defects"] if d["field"] == "info.weather"]
    assert len(weather_nulls) == exp["com_ml_3_weather_null"]
    assert r["Idn-ML-1"]["detail"]["direct"] == exp["idn_direct"]
    # 범주 집계가 정답과 일치 (손상 JPG의 라벨도 라벨로서는 유효하므로 포함)
    assert r["Bal-ML-3"]["detail"]["counts"] == exp["class_counts"]
    # 소수 범주(기준 10 미만) = vehicle, bicycle
    small = {k for k, v in exp["class_counts"].items() if v < 10}
    assert {d["category"] for d in r["Div-ML-3"]["defects"]} == small
    # 야간 보행자 쏠림을 주입했으므로 Bal-ML-7 최대 격차 라벨은 pedestrian
    assert r["Bal-ML-7"]["defects"][0]["label"] == "pedestrian"
    # 완전 복사 이미지 2쌍이 유사 군집으로 묶임
    assert sum(1 for d in r["Sim-ML-1"]["defects"] if d["size"] >= 2) >= 2
    # 2차: 해상도 분포, 라벨 풍부도, 유사 이미지 라벨 불일치
    assert r["Bal-ML-2"]["detail"]["resolutions"] == exp["resolutions"]
    counts = exp["class_counts"]
    assert r["Div-ML-1"]["value"] == pytest.approx(len(counts) / sum(counts.values()))
    flagged = {(d["sample_a"], d["sample_b"]) for d in r["Con-ML-2"]["defects"]}
    for a, b in exp["con_ml_2_inconsistent_pairs"]:
        assert (a, b) in flagged or (b, a) in flagged
    assert 0 < r["Sim-ML-3"]["A"] <= r["Sim-ML-3"]["detail"]["rank_cap"]


def test_at01_emotion():
    r, res, exp = run("emotion")
    assert res["profile"]["samples"] == exp["samples"]
    assert r["Idn-ML-1"]["detail"]["quasi"] == exp["idn_quasi_records"]
    assert r["Con-ML-1"]["A"] == 0
    # 여성 화자 '슬픔' 편향 주입 → 최대 격차 라벨은 슬픔
    top = r["Bal-ML-7"]["defects"][0]
    assert top["label"] == "슬픔" and top["group_high"] == "여성"
    eg = exp["emotion_by_gender"]
    f_rate = eg["여성"]["슬픔"] / sum(eg["여성"].values())
    m_rate = eg["남성"]["슬픔"] / sum(eg["남성"].values())
    assert r["Bal-ML-7"]["value"] == pytest.approx(f_rate - m_rate)
    # 같은 문장 발화의 감정 라벨 일관성: 일치 쌍 2 / 비교 쌍 4
    assert (r["Con-ML-2"]["A"], r["Con-ML-2"]["B"]) == (exp["con_ml_2"]["A"], exp["con_ml_2"]["B"])


# ---------- AT-02 경계값 ----------

def _cfg(root, **fields):
    return config.load({"dataset": {"name": "t", "type": "image", "root": str(root)},
                        "fields": {"categories": "annotation[].class_type", **fields}})


def test_at02_empty_folder(tmp_path):
    res = runner.run(_cfg(tmp_path))
    assert res["profile"]["samples"] == 0
    assert all(r["verdict"] in ("N/A", "미적용", "INFO") for r in res["results"])


def test_at02_labels_only(tmp_path):
    for i in range(3):
        (tmp_path / f"a{i}.json").write_text(json.dumps({"annotation": [{"class_type": "x"}]}), encoding="utf-8")
    r = {x["qm_id"]: x for x in runner.run(_cfg(tmp_path))["results"]}
    assert r["Com-ML-5"]["A"] == 3          # 원천 없는 라벨 3건
    assert r["Bal-ML-3"]["applied"] is False  # 범주 1개 → 균형 정의 불가


def test_at02_missing_root(tmp_path):
    with pytest.raises(FileNotFoundError):
        runner.run(_cfg(tmp_path / "nope"))


def test_at02_labels_only_mode(tmp_path):
    for i in range(3):
        (tmp_path / f"a{i}.json").write_text(json.dumps({"annotation": [{"class_type": "x"}]}), encoding="utf-8")
    cfg = _cfg(tmp_path)
    cfg["dataset"]["labels_only"] = True
    r = {x["qm_id"]: x for x in runner.run(cfg)["results"]}
    assert r["Com-ML-5"]["A"] == 0          # 라벨 전용 모드에서는 원천 누락이 결함 아님


# ---------- AT-03 손상 파일 ----------

def test_at03_corrupt_files(tmp_path):
    (tmp_path / "bad.jpg").write_bytes(b"garbage")
    (tmp_path / "bad.json").write_bytes(b"{not json")
    (tmp_path / "cp.json").write_bytes(json.dumps({"annotation": [{"class_type": "가"}]}, ensure_ascii=False).encode("cp949"))
    Image.new("RGB", (8, 8)).save(tmp_path / "cp.jpg")
    res = runner.run(_cfg(tmp_path))
    reasons = {f["file"]: f["reason"] for f in res["failures"]}
    assert "bad.jpg" in reasons and "bad.json" in reasons
    assert "cp.json" not in reasons  # cp949 라벨은 정상적으로 읽혀야 함


# ---------- AT-05 재현성 ----------

def test_at05_reproducible():
    a, _, _ = run("robot")
    b, _, _ = run("robot")
    assert {k: v["value"] for k, v in a.items()} == {k: v["value"] for k, v in b.items()}

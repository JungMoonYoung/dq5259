"""실데이터 진단 결과를 공개용으로 정리해 results/ 에 저장한다.

AI Hub 원본은 재배포 금지라 저장소에 넣지 않고, 집계 결과만 공개한다.
  - 로컬 경로 제거
  - 결함 목록은 측정값별 상위 20건만
  - 식별가능성(Idn-ML-1) 결함의 준식별자 값은 삭제 (공개 시 재식별 단서가 될 수 있음)

    python tools/export_results.py runs/aihub_robot/run_*.json robot
"""

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "results"
KEEP = 20


def export(src, name):
    r = json.loads(Path(src).read_text(encoding="utf-8"))
    r["dataset"]["root"] = "AI Hub 원본 (재배포 금지로 저장소 미포함)"
    r["config"]["dataset"]["root"] = r["dataset"]["root"]
    for row in r["results"]:
        total = len(row.get("defects", []))
        row["defects"] = row.get("defects", [])[:KEEP]
        if row["qm_id"] == "Idn-ML-1":
            row["defects"] = [{"type": d.get("type"), "kind": d.get("kind"), "reason": d.get("reason")}
                              for d in row["defects"]]
        det = row.get("detail", {})
        if len(det.get("brightness", [])) > 2000:  # 차트용 분포는 2,000개로 균등 표본
            b = det["brightness"]
            det["brightness"] = b[:: len(b) // 2000 + 1]
        if len(det.get("cluster_sizes", [])) > 50:
            det["cluster_sizes"] = det["cluster_sizes"][:50]
        if total > KEEP:
            row["note"] = (row.get("note") or "") + f" · 결함 {total:,}건 중 상위 {KEEP}건만 공개"
    r["failures"] = r.get("failures", [])[:KEEP]
    OUT.mkdir(exist_ok=True)
    dst = OUT / f"{name}.json"
    dst.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(dst, f"{dst.stat().st_size:,} bytes")


if __name__ == "__main__":
    export(sys.argv[1], sys.argv[2])

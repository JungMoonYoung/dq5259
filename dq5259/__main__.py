"""CLI: python -m dq5259 <설정.yaml> [--out 결과폴더]"""

import argparse
import sys
from pathlib import Path

from . import config, report, runner


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dq5259", description="ISO/IEC 5259 기반 AI 학습데이터 품질 평가")
    ap.add_argument("config", help="진단 설정 YAML")
    ap.add_argument("--out", default="runs", help="결과 저장 폴더 (기본: runs)")
    args = ap.parse_args(argv)

    cfg = config.load(args.config)
    try:
        result = runner.run(cfg)
    except FileNotFoundError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 2

    out = Path(args.out)
    run_json = runner.save_run(result, out)
    stem = run_json.stem
    (out / f"{stem}_report.html").write_text(report.html_report(result), encoding="utf-8")
    (out / f"{stem}_defects.csv").write_bytes(report.defects_csv(result))

    s = result["summary"]
    print(f"데이터셋: {cfg['dataset']['name']}  샘플 {result['profile']['samples']}개")
    for r in result["results"]:
        print(f"  {r['qm_id']:<9} {r['verdict']:<5} X={report.fmt(r['value'])}  {r.get('note') or ''}")
    print(f"사전 점검 {'통과' if s['gate_passed'] else '미통과'} / 본 평가 {s['eval_passed']}/{s['eval_judged']} PASS")
    print(f"결과: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

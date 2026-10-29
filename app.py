"""DQ-5259 화면 (SRS 6장). 실행: streamlit run app.py"""

import copy
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from dq5259 import config, report, runner
from dq5259.measures import REGISTRY

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs" / "app"

st.set_page_config(page_title="DQ-5259 데이터 품질 평가", page_icon="📊", layout="wide")
st.title("DQ-5259 · AI 학습데이터 품질 평가")
st.caption("ISO/IEC 5259-2 측정값 · ISO/IEC 5259-3 6.3.9 확인 검토 절차")

VERDICT_ICON = {"PASS": "🟢 PASS", "FAIL": "🔴 FAIL", "INFO": "🔵 INFO", "N/A": "⚪ N/A", "미적용": "⚪ 미적용"}

tab_ds, tab_cfg, tab_res, tab_def, tab_rep = st.tabs(["① 데이터셋", "② 측정 설정", "③ 결과", "④ 결함 상세", "⑤ 보고서"])

# ---------------- ① 데이터셋 ----------------
with tab_ds:
    presets = sorted((ROOT / "configs").glob("*.yaml"))
    choice = st.selectbox("설정 불러오기", presets, format_func=lambda p: p.name)
    uploaded = st.file_uploader("또는 설정 YAML 업로드", type=["yaml", "yml"])
    if uploaded:
        cfg = config.load({**yaml.safe_load(uploaded.read().decode("utf-8"))})
    else:
        cfg = config.load(choice)
    if st.session_state.get("cfg_src") != (uploaded.name if uploaded else str(choice)):
        st.session_state.cfg = cfg
        st.session_state.cfg_src = uploaded.name if uploaded else str(choice)
    cfg = st.session_state.cfg

    c1, c2 = st.columns([2, 1])
    cfg["dataset"]["name"] = c1.text_input("데이터셋 이름", cfg["dataset"]["name"])
    cfg["dataset"]["type"] = c2.selectbox("유형", ["image", "audio"], index=["image", "audio"].index(cfg["dataset"]["type"]))
    cfg["dataset"]["root"] = st.text_input("데이터셋 폴더", cfg["dataset"]["root"])
    with st.expander("라벨 필드 매핑 (fields)"):
        st.code(yaml.safe_dump(cfg["fields"], allow_unicode=True, sort_keys=False), language="yaml")

    if st.button("진단 실행", type="primary"):
        bar = st.progress(0.0, text="프로파일링 중…")
        try:
            result = runner.run(cfg, progress=lambda i, n: bar.progress(i / n, text=f"파일 읽는 중 {i}/{n}"))
        except FileNotFoundError as e:
            st.error(f"{e}")
            st.stop()
        bar.empty()
        st.session_state.result = result
        st.session_state.run_path = runner.save_run(result, RUNS)
        st.success("진단 완료 — ③ 결과 탭에서 확인하세요")

    if "result" in st.session_state:
        p = st.session_state.result["profile"]
        cols = st.columns(5)
        for col, (label, key) in zip(cols, [("샘플", "samples"), ("라벨-원천 쌍", "paired"), ("라벨만", "label_only"),
                                            ("원천만", "source_only"), ("읽기 실패", "read_failures")]):
            col.metric(label, p[key])
        if st.session_state.result["failures"]:
            st.dataframe(pd.DataFrame(st.session_state.result["failures"]), width="stretch")

# ---------------- ② 측정 설정 ----------------
with tab_cfg:
    st.markdown("5259-3 6.3.9: **측정값 식별 → 기준값 문서화**. 적용하지 않는 측정값은 사유를 남깁니다.")
    rows = []
    for qm_id, applied, reason in runner.select(cfg):
        spec = REGISTRY[qm_id]
        m = cfg["measures"].setdefault(qm_id, {})
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
            c1.markdown(f"**{qm_id} {spec.name}**  \n{spec.characteristic} · {spec.clause} · "
                        f"{'사전 점검' if spec.stage == 'gate' else '본 평가'}")
            supported = cfg["dataset"]["type"] in spec.data_types
            m["enabled"] = c2.toggle("적용", m.get("enabled", True) and supported, key=f"en_{qm_id}", disabled=not supported)
            if m.get("direction") != "info":
                m["threshold"] = c3.number_input(f"기준 ({'≤' if m['direction'] == 'max' else '≥'})",
                                                 value=float(m.get("threshold") or 0), step=0.01,
                                                 key=f"th_{qm_id}", format="%.3f")
            else:
                c3.write("정보 제공")
            if not m["enabled"]:
                m["reason"] = c4.text_input("미적용 사유", m.get("reason") or (reason if not supported else ""),
                                            key=f"rs_{qm_id}")
            else:
                c4.caption(spec.formula)
    st.download_button("설정 저장 (YAML)", yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                       file_name="dq5259_config.yaml")

# ---------------- ③ 결과 ----------------
with tab_res:
    if "result" not in st.session_state:
        st.info("① 데이터셋 탭에서 진단을 실행하세요.")
    else:
        res = st.session_state.result
        s = res["summary"]
        c1, c2, c3 = st.columns(3)
        c1.metric("사전 점검", "통과" if s["gate_passed"] else "미통과")
        c2.metric("본 평가 PASS", f"{s['eval_passed']} / {s['eval_judged']}")
        c3.metric("충족률", "-" if s["eval_score"] is None else f"{s['eval_score']}%")
        if not s["gate_passed"]:
            st.warning("사전 점검 미통과 — 본 평가 결과의 신뢰도가 제한됩니다.")

        table = pd.DataFrame([{
            "단계": "사전 점검" if r["stage"] == "gate" else "본 평가", "ID": r["qm_id"], "측정값": r["name"],
            "품질 특성": r["characteristic"], "A": report.fmt(r["A"], 2), "B": report.fmt(r["B"], 2),
            "X": report.fmt(r["value"]), "기준": report.criterion(r), "판정": VERDICT_ICON.get(r["verdict"], r["verdict"]),
            "비고": r.get("note") or ""} for r in res["results"]])
        st.dataframe(table, width="stretch", hide_index=True)

        by_id = {r["qm_id"]: r for r in res["results"]}
        g1, g2 = st.columns(2)
        counts = by_id.get("Bal-ML-3", {}).get("detail", {}).get("counts")
        if counts:
            g1.plotly_chart(px.bar(x=list(counts), y=list(counts.values()), labels={"x": "범주", "y": "개수"},
                                   title="범주 분포 (Bal-ML-3 · Div-ML-3)"), width="stretch")
        bright = by_id.get("Bal-ML-1", {}).get("detail", {}).get("brightness")
        if bright:
            g2.plotly_chart(px.histogram(x=bright, nbins=20, labels={"x": "평균 밝기"},
                                         title="이미지 밝기 분포 (Bal-ML-1)"), width="stretch")
        grp = by_id.get("Bal-ML-7", {}).get("detail", {}).get("table")
        if grp:
            df = pd.DataFrame(grp).fillna(0)
            df = (df / df.sum()).reset_index().melt(id_vars="index", var_name="그룹", value_name="비율")
            st.plotly_chart(px.bar(df, x="index", y="비율", color="그룹", barmode="group",
                                   labels={"index": "라벨"}, title="그룹별 라벨 비율 (Bal-ML-7)"),
                            width="stretch")

# ---------------- ④ 결함 상세 ----------------
with tab_def:
    if "result" in st.session_state:
        res = st.session_state.result
        with_defects = [r for r in res["results"] if r.get("defects")]
        if not with_defects:
            st.success("결함 없음")
        else:
            pick = st.selectbox("측정값", with_defects, format_func=lambda r: f"{r['qm_id']} {r['name']} ({len(r['defects'])}건)")
            st.dataframe(pd.DataFrame(pick["defects"]), width="stretch", hide_index=True)
        st.download_button("결함 목록 CSV", report.defects_csv(res), file_name="defects.csv", mime="text/csv")

# ---------------- ⑤ 보고서 ----------------
with tab_rep:
    if "result" in st.session_state:
        res = st.session_state.result
        html_doc = report.html_report(res)
        st.download_button("보고서 HTML 다운로드", html_doc, file_name="dq5259_report.html", mime="text/html")
        st.iframe(html_doc, height=900)  # 보고서의 데이터 값은 html.escape 처리됨
    st.subheader("실행 이력 (5259-3 6.3.9 검토 기록)")
    runs = runner.load_runs(RUNS) if RUNS.exists() else []
    if runs:
        hist = pd.DataFrame([{"실행": r["run_at"], "데이터셋": r["dataset"]["name"],
                              "샘플": r["profile"]["samples"], "사전 점검": "통과" if r["summary"]["gate_passed"] else "미통과",
                              "본 평가": f"{r['summary']['eval_passed']}/{r['summary']['eval_judged']}"} for r in runs[::-1]])
        st.dataframe(hist, width="stretch", hide_index=True)
    else:
        st.caption("아직 기록이 없습니다.")

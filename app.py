"""DQ-5259 화면 (SRS 6장). 실행: streamlit run app.py"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from dq5259 import config, report, runner, ui
from dq5259.measures import REGISTRY

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs" / "app"

st.set_page_config(page_title="DQ-5259 데이터 품질 평가", page_icon="📊", layout="wide")
st.markdown(f"""<style>{ui.CSS}
.block-container{{padding-top:1.6rem;max-width:1240px}}
[data-testid="stTabs"] button[role="tab"]{{font-size:15px;padding:10px 18px}}
[data-testid="stTabs"] button[aria-selected="true"]{{color:{ui.COLORS['navy']};font-weight:700}}
div[data-testid="stVerticalBlockBorderWrapper"]{{background:#fff;border-radius:12px}}
.stButton button[kind="primary"]{{border-radius:10px;padding:.55rem 1.6rem;font-weight:600}}
</style>""", unsafe_allow_html=True)


def html(s):
    st.markdown(f'<div class="dq">{s}</div>', unsafe_allow_html=True)


html(ui.hero("DQ-5259 · AI 학습데이터 품질 평가",
             "번역하며 익힌 ISO/IEC 5259를 학습데이터에 직접 적용해, ML 전용 품질 특성을 측정하고 판정합니다.",
             ["ISO/IEC 5259-2 측정값", "ISO/IEC 5259-3 6.3.9 확인 검토", "균형 · 다양성 · 식별가능성 · 유사성"]))

tab_ds, tab_cfg, tab_res, tab_def, tab_rep = st.tabs(["① 데이터셋", "② 측정 설정", "③ 결과", "④ 결함 상세", "⑤ 보고서"])

# ---------------- ① 데이터셋 ----------------
with tab_ds:
    html(ui.section("데이터셋 지정", "라벨·원천 폴더와 라벨 구조 설정"))
    with st.container(border=True):
        c0, c00 = st.columns([2, 1])
        presets = sorted((ROOT / "configs").glob("*.yaml"))
        default = next((i for i, p in enumerate(presets) if p.stem == "synthetic_robot"), 0)
        choice = c0.selectbox("설정 불러오기", presets, index=default, format_func=lambda p: p.name)
        uploaded = c00.file_uploader("또는 설정 YAML 업로드", type=["yaml", "yml"])
        src = uploaded.name if uploaded else str(choice)
        if st.session_state.get("cfg_src") != src:
            st.session_state.cfg = (config.load(yaml.safe_load(uploaded.read().decode("utf-8")))
                                    if uploaded else config.load(choice))
            st.session_state.cfg_src = src
        cfg = st.session_state.cfg

        c1, c2 = st.columns([2, 1])
        cfg["dataset"]["name"] = c1.text_input("데이터셋 이름", cfg["dataset"]["name"])
        cfg["dataset"]["type"] = c2.selectbox("유형", ["image", "audio"],
                                              index=["image", "audio"].index(cfg["dataset"]["type"]),
                                              format_func=lambda t: {"image": "이미지", "audio": "음성"}[t])
        cfg["dataset"]["root"] = st.text_input("데이터셋 폴더", cfg["dataset"]["root"])
        with st.expander("라벨 필드 매핑 (fields)"):
            st.code(yaml.safe_dump(cfg["fields"], allow_unicode=True, sort_keys=False), language="yaml")
        run_clicked = st.button("진단 실행", type="primary")

    if run_clicked:
        bar = st.progress(0.0, text="프로파일링 중…")
        try:
            result = runner.run(cfg, progress=lambda i, n: bar.progress(i / n, text=f"파일 읽는 중 {i}/{n}"))
        except FileNotFoundError as e:
            bar.empty()
            st.error(str(e))
            st.stop()
        bar.empty()
        st.session_state.result = result
        runner.save_run(result, RUNS)
        st.toast("진단 완료 — ③ 결과 탭에서 확인하세요")

    if "result" in st.session_state:
        p = st.session_state.result["profile"]
        html(ui.section("프로파일", "라벨-원천 쌍 매칭 결과"))
        html(ui.kpis(ui.kpi("샘플", f"{p['samples']:,}"), ui.kpi("라벨-원천 쌍", f"{p['paired']:,}"),
                     ui.kpi("라벨만", p["label_only"]), ui.kpi("원천만", p["source_only"]),
                     ui.kpi("읽기 실패", p["read_failures"])))
        if st.session_state.result["failures"]:
            st.dataframe(pd.DataFrame(st.session_state.result["failures"]), width="stretch", hide_index=True)

# ---------------- ② 측정 설정 ----------------
with tab_cfg:
    html(ui.section("측정값 식별 · 기준값 문서화", "ISO/IEC 5259-3 6.3.9 — 적용하지 않는 측정값은 사유를 남깁니다"))
    for stage, label in (("gate", "사전 점검 · 일반 데이터 품질"), ("eval", "본 평가 · ML 전용 데이터 품질")):
        st.markdown(f"**{label}**")
        for qm_id, applied, reason in runner.select(cfg):
            spec = REGISTRY[qm_id]
            if spec.stage != stage:
                continue
            m = cfg["measures"].setdefault(qm_id, {})
            supported = cfg["dataset"]["type"] in spec.data_types
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 1, 1.2, 3.5])
                c1.markdown(f'<div class="dq"><span class="dq-id">{ui.esc(qm_id)}</span> '
                            f'<b>{ui.esc(spec.name)}</b><div class="dq-muted">{ui.esc(spec.characteristic)} · '
                            f'{ui.esc(spec.clause)}</div></div>', unsafe_allow_html=True)
                m["enabled"] = c2.toggle("적용", m.get("enabled", True) and supported, key=f"en_{qm_id}",
                                         disabled=not supported)
                if m.get("direction") != "info":
                    m["threshold"] = c3.number_input(f"기준 ({'≤' if m['direction'] == 'max' else '≥'})",
                                                     value=float(m.get("threshold") or 0), step=0.01,
                                                     key=f"th_{qm_id}", format="%.3f")
                else:
                    c3.markdown('<div class="dq dq-muted" style="padding-top:30px">정보 제공</div>',
                                unsafe_allow_html=True)
                if not m["enabled"]:
                    m["reason"] = c4.text_input("미적용 사유", m.get("reason") or (reason if not supported else ""),
                                                key=f"rs_{qm_id}")
                else:
                    c4.markdown(f'<div class="dq dq-muted" style="padding-top:8px">{ui.esc(spec.formula)}</div>',
                                unsafe_allow_html=True)
    st.download_button("설정 저장 (YAML)", yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                       file_name="dq5259_config.yaml")

# ---------------- ③ 결과 ----------------
with tab_res:
    if "result" not in st.session_state:
        st.info("① 데이터셋 탭에서 진단을 실행하세요.")
    else:
        res = st.session_state.result
        s, p = res["summary"], res["profile"]
        rows = res["results"]
        html(ui.section("종합 결과", res["dataset"]["name"]))
        html(ui.kpis(ui.kpi("샘플", f"{p['samples']:,}", f"라벨-원천 쌍 {p['paired']:,}"),
                     ui.kpi("사전 점검", "통과" if s["gate_passed"] else "미통과"),
                     ui.kpi("본 평가 충족", f"{s['eval_passed']} / {s['eval_judged']}", "판정 대상 측정값"),
                     ui.score_kpi("충족률", s["eval_score"], "본 평가 기준")))
        if not s["gate_passed"]:
            html(ui.banner("사전 점검 미통과 — 라벨 누락·중복 등을 먼저 해소해야 본 평가 결과를 신뢰할 수 있습니다.", "FAIL"))

        html(ui.section("사전 점검", "일반 데이터 품질 · 평가 가능 여부 확인"))
        html(ui.cards([r for r in rows if r["stage"] == "gate"]))
        html(ui.section("본 평가", "ML 전용 데이터 품질 · ISO/IEC 5259-2 6.5"))
        html(ui.cards([r for r in rows if r["stage"] == "eval"]))

        by_id = {r["qm_id"]: r for r in rows}
        charts = []
        counts = by_id.get("Bal-ML-3", {}).get("detail", {}).get("counts")
        if counts:
            min_count = by_id.get("Div-ML-3", {}).get("detail", {}).get("min_count")
            fig = px.bar(x=list(counts), y=list(counts.values()), labels={"x": "범주", "y": "개수"},
                         title="범주 분포 · Bal-ML-3 / Div-ML-3")
            if min_count:
                fig.add_hline(y=min_count, line_dash="dot", line_color=ui.COLORS["FAIL"],
                              annotation_text=f"최소 기준 {min_count}", annotation_position="top right")
            charts.append(fig)
        bright = by_id.get("Bal-ML-1", {}).get("detail", {}).get("brightness")
        if bright:
            charts.append(px.histogram(x=bright, nbins=20, labels={"x": "평균 밝기 (0~255)", "count": "이미지 수"},
                                       title="이미지 밝기 분포 · Bal-ML-1"))
        grp = by_id.get("Bal-ML-7", {}).get("detail", {}).get("table")
        if grp:
            df = pd.DataFrame(grp).fillna(0)
            df = (df / df.sum()).reset_index().melt(id_vars="index", var_name="그룹", value_name="비율")
            charts.append(px.bar(df, x="index", y="비율", color="그룹", barmode="group",
                                 labels={"index": "라벨"}, title="그룹별 라벨 비율 · Bal-ML-7"))
        if charts:
            html(ui.section("분포", "측정값 근거 데이터"))
            for i in range(0, len(charts), 2):
                cols = st.columns(2)
                for col, fig in zip(cols, charts[i:i + 2]):
                    with col.container(border=True):
                        st.plotly_chart(ui.style_fig(fig), width="stretch")

        with st.expander("측정값 표로 보기"):
            st.dataframe(pd.DataFrame([{
                "단계": "사전 점검" if r["stage"] == "gate" else "본 평가", "ID": r["qm_id"], "측정값": r["name"],
                "A": report.fmt(r["A"], 2), "B": report.fmt(r["B"], 2), "X": report.fmt(r["value"]),
                "기준": report.criterion(r), "판정": ui.VERDICT_KO.get(r["verdict"], r["verdict"]),
                "비고": r.get("note") or ""} for r in rows]), width="stretch", hide_index=True)

# ---------------- ④ 결함 상세 ----------------
with tab_def:
    if "result" not in st.session_state:
        st.info("① 데이터셋 탭에서 진단을 실행하세요.")
    else:
        res = st.session_state.result
        with_defects = [r for r in res["results"] if r.get("defects")]
        html(ui.section("결함 상세", f"결함이 있는 측정값 {len(with_defects)}개"))
        if not with_defects:
            html(ui.banner("결함 없음", "PASS"))
        else:
            pick = st.radio("측정값", with_defects, horizontal=True,
                            format_func=lambda r: f"{r['qm_id']} · {len(r['defects'])}건")
            html(ui.measure_card(pick))
            st.dataframe(pd.DataFrame(pick["defects"]), width="stretch", hide_index=True)
            advice = report.ADVICE.get(pick["qm_id"])
            if advice and pick["verdict"] == "FAIL":
                html(ui.banner(f"조치 권고 — {advice}", "INFO"))
        st.download_button("결함 목록 CSV", report.defects_csv(res), file_name="defects.csv", mime="text/csv")

# ---------------- ⑤ 보고서 ----------------
with tab_rep:
    if "result" in st.session_state:
        res = st.session_state.result
        html_doc = report.html_report(res)
        html(ui.section("평가 보고서", "시험성적서 형식 · HTML"))
        st.download_button("보고서 HTML 다운로드", html_doc, file_name="dq5259_report.html", mime="text/html",
                           type="primary")
        st.iframe(html_doc, height=900)  # 보고서의 데이터 값은 html.escape 처리됨
    html(ui.section("실행 이력", "ISO/IEC 5259-3 6.3.9 검토 기록 유지"))
    runs = runner.load_runs(RUNS) if RUNS.exists() else []
    if runs:
        st.dataframe(pd.DataFrame([{
            "실행": r["run_at"], "데이터셋": r["dataset"]["name"], "샘플": r["profile"]["samples"],
            "사전 점검": "통과" if r["summary"]["gate_passed"] else "미통과",
            "본 평가": f"{r['summary']['eval_passed']}/{r['summary']['eval_judged']}",
            "충족률": r["summary"]["eval_score"]} for r in runs[::-1]]), width="stretch", hide_index=True)
    else:
        st.caption("아직 기록이 없습니다.")

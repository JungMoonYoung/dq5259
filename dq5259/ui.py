"""화면·보고서 공통 디자인 (차분한 네이비 톤).

보고서(HTML)와 Streamlit 화면이 같은 카드·색을 쓰도록 한곳에 둔다.
"""

import html
import math

COLORS = {
    "navy": "#0b2e59", "navy2": "#1d4673", "accent": "#3b6ea5",
    "bg": "#f4f6f9", "card": "#ffffff", "line": "#dde3ea", "text": "#1f2933", "muted": "#6b7785",
    "PASS": "#2f7d5b", "FAIL": "#b4443c", "INFO": "#4a6fa5", "N/A": "#9aa5b1", "미적용": "#9aa5b1",
}
VERDICT_BG = {"PASS": "#e6f2ec", "FAIL": "#f7e7e5", "INFO": "#e8eef6", "N/A": "#eef1f4", "미적용": "#eef1f4"}
VERDICT_KO = {"PASS": "충족", "FAIL": "미충족", "INFO": "정보", "N/A": "산출 불가", "미적용": "미적용"}

CSS = """
.dq{font-family:'Pretendard','Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:%(text)s}
.dq-hero{background:linear-gradient(120deg,%(navy)s 0%%,%(navy2)s 100%%);color:#fff;border-radius:14px;
  padding:26px 30px;margin-bottom:18px;position:relative;overflow:hidden}
.dq-hero:after{content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%%;
  background:rgba(255,255,255,.06)}
.dq-hero h1{margin:0 0 6px;font-size:26px;font-weight:700;letter-spacing:-.3px;color:#fff;border:0;padding:0}
.dq-hero p{margin:0;opacity:.82;font-size:14px}
.dq-chips{margin-top:14px;display:flex;gap:8px;flex-wrap:wrap}
.dq-chip{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:999px;
  padding:3px 11px;font-size:12px}
.dq-sec{display:flex;align-items:baseline;gap:10px;margin:26px 0 12px}
.dq-sec b{font-size:18px;color:%(navy)s}
.dq-sec span{font-size:12px;color:%(muted)s;letter-spacing:.3px}
.dq-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.dq-kpi{background:%(card)s;border:1px solid %(line)s;border-radius:12px;padding:14px 16px;border-top:3px solid %(accent)s}
.dq-kpi small{display:block;color:%(muted)s;font-size:12px}
.dq-kpi b{display:block;font-size:26px;color:%(navy)s;margin-top:2px;letter-spacing:-.5px}
.dq-kpi i{font-style:normal;font-size:12px;color:%(muted)s}
.dq-score{display:flex;align-items:center;gap:14px}
.dq-ring{width:64px;height:64px;border-radius:50%%;display:grid;place-items:center;flex:none}
.dq-ring span{width:48px;height:48px;border-radius:50%%;background:#fff;display:grid;place-items:center;
  font-weight:700;font-size:13px;color:%(navy)s}
.dq-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.dq-card{background:%(card)s;border:1px solid %(line)s;border-radius:12px;padding:14px 16px 12px;
  border-left:4px solid var(--vc)}
.dq-card .top{display:flex;justify-content:space-between;align-items:center}
.dq-id{font-family:Consolas,monospace;font-size:12px;color:%(accent)s;background:#eef3f9;border-radius:6px;padding:2px 7px}
.dq-pill{font-size:11px;font-weight:700;border-radius:999px;padding:3px 10px;color:var(--vc);background:var(--vb)}
.dq-card h4{margin:8px 0 2px;font-size:15px;color:%(text)s}
.dq-card .sub{font-size:11.5px;color:%(muted)s}
.dq-val{font-size:26px;font-weight:700;color:%(navy)s;margin:8px 0 6px;letter-spacing:-.5px}
.dq-val small{font-size:12px;font-weight:400;color:%(muted)s;margin-left:6px}
.dq-bar{position:relative;height:7px;background:#edf1f5;border-radius:4px;margin:2px 0 8px}
.dq-bar .fill{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--vc)}
.dq-bar .tick{position:absolute;top:-4px;width:2px;height:15px;background:%(navy)s;opacity:.65}
.dq-card .foot{display:flex;justify-content:space-between;font-size:11.5px;color:%(muted)s;border-top:1px dashed %(line)s;padding-top:7px}
.dq-card .note{font-size:11.5px;color:%(muted)s;margin-top:6px;line-height:1.45}
.dq-banner{border-radius:10px;padding:10px 14px;font-size:13px;margin:12px 0}
.dq-table{border-collapse:collapse;width:100%%;font-size:12.5px;background:#fff;border-radius:10px;overflow:hidden}
.dq-table th{background:#eef2f7;color:%(navy)s;font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid %(line)s}
.dq-table td{padding:7px 10px;border-bottom:1px solid #eef1f4;vertical-align:top}
.dq-table tr:last-child td{border-bottom:0}
.dq-muted{color:%(muted)s;font-size:12px}
""" % COLORS


def esc(v):
    return html.escape(str(v))


def fmt(v, digits=4):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        if math.isinf(v):
            return "∞"
        if v.is_integer():
            return str(int(v))
        return f"{v:.{digits}f}"
    return str(v)


def criterion(r):
    th, d = r.get("threshold"), r.get("direction")
    if d == "info" or th is None:
        return "정보 제공"
    return f"≤ {th}" if d == "max" else f"≥ {th}"


def hero(title, subtitle, chips=()):
    chip_html = "".join(f'<span class="dq-chip">{esc(c)}</span>' for c in chips)
    return (f'<div class="dq-hero"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p>'
            f'<div class="dq-chips">{chip_html}</div></div>')


def section(title, caption=""):
    return f'<div class="dq-sec"><b>{esc(title)}</b><span>{esc(caption)}</span></div>'


def kpi(label, value, hint=""):
    return f'<div class="dq-kpi"><small>{esc(label)}</small><b>{esc(value)}</b><i>{esc(hint)}</i></div>'


def score_kpi(label, score, hint=""):
    pct = 0 if score is None else max(0, min(100, score))
    ring = f"conic-gradient({COLORS['accent']} {pct * 3.6}deg, #e6ebf1 0)"
    text = "-" if score is None else f"{score:g}%"
    return (f'<div class="dq-kpi"><div class="dq-score"><div class="dq-ring" style="background:{ring}">'
            f'<span>{esc(text)}</span></div><div><small>{esc(label)}</small><i>{esc(hint)}</i></div></div></div>')


def kpis(*cards):
    return f'<div class="dq-kpis">{"".join(cards)}</div>'


def banner(text, kind="INFO"):
    return (f'<div class="dq-banner" style="background:{VERDICT_BG[kind]};color:{COLORS[kind]};'
            f'border:1px solid {COLORS[kind]}33">{esc(text)}</div>')


def _gauge(r):
    """값과 기준선을 같은 축에 그린다. 0~1 비율형은 0~1, 그 외는 max(값, 기준)×1.3 범위."""
    v, th = r.get("value"), r.get("threshold")
    if not isinstance(v, (int, float)) or (isinstance(v, float) and math.isinf(v)):
        return ""
    top = 1.0 if v <= 1 and (th is None or th <= 1) else max(v, th or 0) * 1.3 or 1
    fill = max(0.0, min(1.0, v / top)) * 100
    tick = "" if th is None or r.get("direction") == "info" else \
        f'<div class="tick" style="left:calc({min(1.0, th / top) * 100:.1f}% - 1px)"></div>'
    return f'<div class="dq-bar"><div class="fill" style="width:{fill:.1f}%"></div>{tick}</div>'


def measure_card(r):
    v = r["verdict"]
    style = f'--vc:{COLORS.get(v, COLORS["N/A"])};--vb:{VERDICT_BG.get(v, VERDICT_BG["N/A"])}'
    if r.get("applied"):
        value = fmt(r.get("value"))
        ab = f'A {fmt(r.get("A"), 2)} · B {fmt(r.get("B"), 2)}' if r.get("A") is not None else "분포 기반 산출"
        body = (f'<div class="dq-val">{esc(value)}<small>기준 {esc(criterion(r))}</small></div>{_gauge(r)}'
                f'<div class="foot"><span>{esc(ab)}</span><span>결함 {len(r.get("defects", []))}건</span></div>')
    else:
        body = '<div class="dq-val" style="color:#9aa5b1">—</div>'
    note = f'<div class="note">{esc(r.get("note"))}</div>' if r.get("note") else ""
    return (f'<div class="dq-card" style="{style}"><div class="top"><span class="dq-id">{esc(r["qm_id"])}</span>'
            f'<span class="dq-pill">{esc(VERDICT_KO.get(v, v))}</span></div>'
            f'<h4>{esc(r["name"])}</h4><div class="sub">{esc(r["characteristic"])} · {esc(r["clause"])}</div>'
            f'{body}{note}</div>')


def cards(results):
    return f'<div class="dq-grid">{"".join(measure_card(r) for r in results)}</div>'


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table class="dq-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


PLOT_COLORS = ["#0b2e59", "#3b6ea5", "#7c9cc4", "#a9bcd6", "#5b7f6e", "#c9a66b"]


def style_fig(fig):
    fig.update_layout(template="simple_white", colorway=PLOT_COLORS, font_family="Malgun Gothic",
                      title_font_color=COLORS["navy"], title_font_size=15,
                      margin=dict(l=10, r=10, t=48, b=10), height=330,
                      legend=dict(orientation="h", y=1.08, x=1, xanchor="right"))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#eef1f4", showgrid=True)
    return fig

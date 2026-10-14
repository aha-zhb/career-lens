"""Render V0.2 points/ranges or a no-scale relationship diagram."""
import math
import textwrap
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Polygon
import numpy as np
from render_radar import find_chinese_font
from validate_input import bounds

BLUE, ORANGE, INK, MUTED = "#2673D9", "#C65D0A", "#183149", "#536577"

def selected_dimensions(data):
    market = data["market_model"]
    index = {d["id"]: d for d in market["dimensions"]}
    return [index[i] for i in market.get("radar_dimension_ids", list(index))]

def chart_values(data):
    dims = selected_dimensions(data)
    personal = {a["dimension_id"]: a for a in data["candidate_evidence"]["assessments"]}
    market = [bounds(d, "market_level", "market_level_range") for d in dims]
    candidate = [bounds(personal.get(d["id"], {}), "score", "score_range")
                 if personal.get(d["id"], {}).get("status") != "unknown" else None for d in dims]
    return dims, market, candidate, personal

def adjacent_segments(values):
    """Only connect neighboring point ratings; never bridge a missing/range axis."""
    n = len(values)
    return [(i, (i + 1) % n) for i in range(n)
            if values[i] and values[(i + 1) % n]
            and values[i][0] == values[i][1]
            and values[(i + 1) % n][0] == values[(i + 1) % n][1]]

def choose_mode(data):
    dims, market, candidate, _ = chart_values(data)
    choice = data["report_content"].get("chart_mode", "auto")
    if choice == "radar" and not any(market):
        raise ValueError("Radar requires at least one supported market rating; use relation instead.")
    if choice != "auto": return choice
    threshold = math.ceil(len(dims) / 2)
    return "radar" if sum(bool(v) for v in market) >= threshold and sum(bool(v) for v in candidate) >= threshold else "relation"

def level_text(obj, point="market_level", interval="market_level_range"):
    band = bounds(obj, point, interval)
    if not band: return "任务参照" if point == "market_level" else "经历说明"
    return f"L{band[0]}" if band[0] == band[1] else f"L{band[0]}–L{band[1]}"

def render(data, output):
    font = find_chinese_font()
    if not font:
        raise RuntimeError("中文字体不可用；请安装 Noto Sans CJK SC、PingFang 或黑体后重试。")
    fp = lambda size: FontProperties(fname=font, size=size)
    dims, market, candidate, personal = chart_values(data)
    if not 3 <= len(dims) <= 8: raise ValueError("Overview requires 3–8 selected dimensions.")
    mode = choose_mode(data)
    fig = plt.figure(figsize=(3.9, 4.3), dpi=300, facecolor="white")
    label = data["market_model"]["reference_label"]
    title = "【合成演示】" if data.get("synthetic") else ""
    title += ("岗位参照与个人行为" if mode == "radar" else "岗位任务与个人经历") if personal else "岗位任务地图"
    fig.text(.5, .965, title, ha="center", fontproperties=fp(12), color=INK)
    if mode == "radar":
        ax = fig.add_axes([.18, .20, .64, .55], projection="polar")
        ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1); ax.set_ylim(0, 5)
        angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False)
        ax.set_xticks(angles)
        ax.set_xticklabels([textwrap.fill(d["name"], 8) for d in dims], fontproperties=fp(11), color=INK)
        for tick in ax.get_xticklabels(): tick.set_bbox(dict(facecolor="white",edgecolor="none",pad=1))
        ax.tick_params(axis="x", pad=10)
        ax.set_yticks(range(1, 6)); ax.set_yticklabels(list("12345"), fontproperties=fp(8.5), color=MUTED)
        ax.grid(color="#DFE6EE", linewidth=.7); ax.spines["polar"].set_color("#DFE6EE")
        for values, color, series_label in ((market, BLUE, "岗位参照"), (candidate, ORANGE, "个人已支持行为")):
            if color == ORANGE and not personal: continue
            for i, j in adjacent_segments(values):
                a1, a2 = angles[i], angles[j] if j else 2 * np.pi
                ax.plot([a1, a2], [values[i][0], values[j][0]], color=color, linewidth=1.7)
            for i, band in enumerate(values):
                if band:
                    if band[0] == band[1]: ax.scatter([angles[i]], [band[0]], color=color, s=20, zorder=4)
                    else:
                        ax.plot([angles[i], angles[i]], band, color=color, linewidth=4, solid_capstyle="butt")
                        ax.scatter([angles[i], angles[i]], band, facecolors="white", edgecolors=color, s=15, zorder=4)
            if all(v and v[0] == v[1] for v in values):
                ax.fill(np.r_[angles, angles[0]], [v[0] for v in values] + [values[0][0]], color=color, alpha=.07)
            ax.plot([], [], color=color, linewidth=1.7, label=series_label)
        fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.5, .913),
                   ncol=2, frameon=False, prop=fp(9.5), columnspacing=.8)
        note = "线点：行为等级；轴上短条：有依据的等级范围。\n" + ("未标个人点的维度以经历说明，不表示低分。" if personal else "仅展示岗位参照，不评价个人能力。")
    else:
        ax = fig.add_axes([0, .14, 1, .74]); ax.set_xlim(0, 390); ax.set_ylim(0, 350); ax.set_aspect("equal"); ax.axis("off")
        angles = np.linspace(np.pi/2, np.pi/2-2*np.pi, len(dims), endpoint=False)
        center = np.array([195, 175])
        vertices = np.array([center + 72*np.array([np.cos(a), np.sin(a)]) for a in angles])
        ax.add_patch(Polygon(vertices, closed=True, facecolor="#EEF4FB", edgecolor=BLUE, linewidth=1.5))
        center_text = ("六维任务\n对应\n个人经历" if len(dims)==6 else "岗位任务\n对应\n个人经历") if personal else "六维任务\n岗位地图"
        ax.text(195,175,center_text, ha="center",va="center",fontproperties=fp(11),color=INK,linespacing=1.5)
        for i,d in enumerate(dims):
            p=center + 130*np.array([np.cos(angles[i]),np.sin(angles[i])])
            ax.plot([vertices[i][0],p[0]],[vertices[i][1],p[1]],color="#BDCEE2",linewidth=1)
            ax.text(p[0],p[1]+8,textwrap.fill(d["name"],8),ha="center",va="bottom",fontproperties=fp(11),color=INK,bbox=dict(facecolor="white",edgecolor="none",pad=1))
            record=personal.get(d["id"],{})
            summary=record.get("summary") or (d["role_tasks"][0] if not personal else "优先整理相关结果")
            if len(summary)>22: summary=summary[:21]+"…"
            ax.text(p[0],p[1]-4,textwrap.fill(summary,8),ha="center",va="top",fontproperties=fp(9),color=ORANGE if personal else BLUE,bbox=dict(facecolor="white",edgecolor="none",pad=1))
        note="无刻度：组织任务与经历，不表示能力高低。"
    fig.text(.5,.080,"\n".join(textwrap.wrap(label,26)),ha="center",va="bottom",fontproperties=fp(8),color=BLUE)
    fig.text(.5,.009,note,ha="center",va="bottom",fontproperties=fp(8),color=MUTED,linespacing=1.3)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,facecolor="white"); plt.close(fig)
    return {"mode":mode,"market_rated":sum(bool(x) for x in market),"personal_rated":sum(bool(x) for x in candidate),
            "personal_segments":adjacent_segments(candidate),"dimensions":[d["id"] for d in dims]}

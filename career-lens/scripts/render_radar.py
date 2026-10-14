#!/usr/bin/env python3
"""Render the evidence-backed market/personal comparison as a Chinese PNG."""
import argparse
import json
import sys
import textwrap
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from validate_input import validate

FONT_CANDIDATES = ["PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", "Source Han Sans SC", "WenQuanYi Zen Hei", "Arial Unicode MS"]

def find_chinese_font():
    for family in FONT_CANDIDATES:
        try:
            path = font_manager.findfont(family, fallback_to_default=False)
            if Path(path).is_file(): return path
        except (ValueError, RuntimeError):
            continue
    for path in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).is_file(): return path
    return None

def render(data, output):
    font = find_chinese_font()
    if not font:
        raise RuntimeError("找不到可用的中文字体。请安装 PingFang SC、Noto Sans CJK SC、Source Han Sans SC 或 WenQuanYi Zen Hei 后重试。")
    all_dims = data["market_model"]["dimensions"]
    radar_ids = data["market_model"].get("radar_dimension_ids")
    dims = [d for d in all_dims if d["id"] in radar_ids] if radar_ids else all_dims
    if not 3 <= len(dims) <= 8:
        raise RuntimeError("雷达图只展示3–8个可读一级维度；完整能力树保留在报告表格中。")
    if data["market_model"].get("market_confidence") != "sufficient_for_rating" or any(d.get("market_level") is None for d in dims):
        raise RuntimeError("市场等级尚不足以绘图；请用岗位要求与证据状态表格替代雷达图。")
    personal = {p["dimension_id"]: p for p in data["candidate_evidence"]["assessments"]}
    n = len(dims)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    # Fixed portrait canvas: 390px display width keeps labels around 12px.
    # Avoid tight bounding boxes, which can widen long titles and shrink text.
    fig = plt.figure(figsize=(3.9, 6.4), dpi=300)
    ax = fig.add_axes([0.17, 0.32, 0.66, 0.44], projection="polar")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], color="#667085", fontsize=8)
    labels = [textwrap.fill(d["name"], width=7) for d in dims]
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.tick_params(axis="x", pad=12)
    for label in ax.get_xticklabels(): label.set_fontproperties(font_manager.FontProperties(fname=font, size=9))
    for label in ax.get_yticklabels(): label.set_fontproperties(font_manager.FontProperties(fname=font, size=8))
    ax.grid(color="#D9DEE8", linewidth=0.8)
    market = [d["market_level"] for d in dims]
    ma = np.r_[angles, angles[0]]
    mv = np.r_[market, market[0]]
    ax.plot(ma, mv, color="#2673D9", linewidth=1.8, label="市场要求")
    ax.fill(ma, mv, color="#2673D9", alpha=0.12)
    ax.scatter(angles, market, color="#2673D9", s=15, zorder=4)
    pvals = [personal.get(d["id"], {}).get("score") if personal.get(d["id"], {}).get("status") != "unknown" else None for d in dims]
    # Draw only immediate neighboring known points. Never close a partial series or bridge an unknown axis.
    for i in range(n):
        j = (i + 1) % n
        if pvals[i] is not None and pvals[j] is not None:
            ax.plot([angles[i], angles[j]], [pvals[i], pvals[j]], color="#E97824", linewidth=1.8)
    for i, val in enumerate(pvals):
        if val is not None: ax.scatter([angles[i]], [val], color="#E97824", s=20, zorder=5)
    if all(v is not None for v in pvals):
        ax.fill(np.r_[angles, angles[0]], np.r_[pvals, pvals[0]], color="#E97824", alpha=0.1)
    ax.plot([], [], color="#E97824", linewidth=1.8, label="个人材料证据")
    unknown = [dims[i]["name"] for i, v in enumerate(pvals) if v is None]
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(0.5, 0.865), ncol=2, frameon=False, columnspacing=1.2, handlelength=1.6, prop=font_manager.FontProperties(fname=font, size=9))
    chart_title = "AI应用产品经理\n市场要求与个人材料证据"
    if data.get("synthetic"): chart_title = "【合成演示】" + chart_title
    fig.suptitle(chart_title, y=0.975, fontproperties=font_manager.FontProperties(fname=font, size=12))
    gaps = [(market[i] - v, dims[i]["name"]) for i, v in enumerate(pvals) if v is not None and market[i] > v]
    note_lines = []
    if gaps:
        gap, name = max(gaps)
        note_lines.append(textwrap.fill(f"最大已支持等级差：{name}（{gap}级）", width=23))
    note_lines.append("个人等级仅由材料支持，非第三方核验。")
    if unknown:
        note_lines.append(textwrap.fill("待验证：" + "、".join(unknown), width=23))
        note_lines.append("未知不画橙色点，不以低分或零分补位。")
    if data.get("synthetic"): note_lines.append("合成数据仅展示图表，不用于职业结论。")
    fig.text(0.5, 0.035, "\n".join(note_lines), ha="center", va="bottom", linespacing=1.35, color="#475467", fontproperties=font_manager.FontProperties(fname=font, size=9))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor="white")
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path); ap.add_argument("output", type=Path)
    args = ap.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        errors = validate(data)
        if errors:
            print("INVALID")
            for error in errors: print(f"- {error}")
            return 1
        render(data, args.output)
    except RuntimeError as exc: print(f"ERROR: {exc}", file=sys.stderr); return 1
    print(f"PNG: {args.output}"); return 0

if __name__ == "__main__": raise SystemExit(main())

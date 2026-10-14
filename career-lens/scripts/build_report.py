#!/usr/bin/env python3
"""Validate input, then build a five-part Markdown report and optional matching PNG."""
import argparse, hashlib, json, sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from validate_input import validate
from render_radar import render
from render_overview import render as render_overview, level_text
from report_export import evidence_html, export_pdf

ROOT = Path(__file__).resolve().parents[1]

def build_v2(data, source, output, pdf=False):
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
    chart = output.with_name(output.stem + "-" + digest + ".png")
    chart_path = None
    chart_note = ""
    try:
        metadata = render_overview(data, chart)
        chart_path = chart.name
    except RuntimeError as exc:
        metadata = {"mode":"text", "reason":str(exc)}
        chart_note = "图示所需中文字体不可用；可阅读下方结论及研究依据。"
    companion = output.with_name(output.stem + "-evidence.md")
    companion_html = companion.with_suffix(".html")
    html = output.with_suffix(".html")
    pdf_file = output.with_suffix(".pdf") if pdf else None
    ctx = dict(data, chart_path=chart_path, chart_note=chart_note,
               personal_available=bool(data["candidate_evidence"]["materials"]),
               chart_alt=("有依据的岗位与个人行为等级；缺失点不表示低分" if metadata["mode"] == "radar" else "六维岗位任务与个人经历关系，没有能力刻度"),
               evidence_filename=companion.name, evidence_html_filename=companion_html.name,
               html_filename=html.name, markdown_filename=output.name,
               pdf_filename=pdf_file.name if pdf_file else None,
               source_map={s["id"]:s for s in data["sources"]},
               dimension_map={d["id"]:d for d in data["market_model"]["dimensions"]},
               evidence_map={e["evidence_id"]:e for e in data["candidate_evidence"]["evidence"]},
               level_text=level_text,
               layer_labels={"target_market":"目标地区招聘", "role_benchmark":"同类责任／任务参照", "work_practice":"工作实践"},
               stage_labels={"concept":"方案阶段", "prototype":"可运行原型", "trial":"试用阶段", "launched":"正式上线", "operating":"持续运营", "unknown":"材料未明确项目阶段"})
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined, autoescape=False)
    evidence_md = env.get_template("evidence-v02.md.j2").render(**ctx)
    companion.write_text(evidence_md.rstrip()+"\n", encoding="utf-8")
    companion_html.write_text(evidence_html(evidence_md, "Career Lens研究与判断依据"), encoding="utf-8")
    output.write_text(env.get_template("report-v02.md.j2").render(**ctx).rstrip()+"\n", encoding="utf-8")
    env.autoescape = True
    html.write_text(env.get_template("report-v02.html.j2").render(**ctx), encoding="utf-8")
    output.with_suffix(".chart.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if pdf_file: export_pdf(data, pdf_file, chart if chart_path else None, companion_html)
    print(f"REPORT: {output}\nHTML: {html}\nEVIDENCE: {companion}\nCHART: {metadata['mode']}")
    if pdf_file: print(f"PDF: {pdf_file}")
    return 0

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path); ap.add_argument("output", type=Path)
    ap.add_argument("--pdf", action="store_true", help="Also export V0.2 as PDF (install the pdf extra)")
    args = ap.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        errors = validate(data)
        if errors:
            print("INVALID")
            for error in errors: print(f"- {error}")
            return 1
        if data.get("schema_version") == "0.2":
            return build_v2(data, args.input, args.output, args.pdf)
        if args.pdf:
            raise ValueError("PDF export requires a V0.2 diagnosis; V0.1 Markdown export remains supported.")
        digest = hashlib.sha256(args.input.read_bytes()).hexdigest()[:10]
        chart_file = args.output.with_name(args.output.stem + "-" + digest + ".png")
        chart_path = None
        chart_note = "市场证据不足，未绘制雷达图；本报告用完整能力树与状态表呈现。"
        if data["market_model"]["market_confidence"] == "sufficient_for_rating" and all(d["market_level"] is not None for d in data["market_model"]["dimensions"]):
            try:
                render(data, chart_file)
                chart_path = chart_file.name
                chart_note = f"雷达图已按同一份诊断数据生成：{chart_path}。"
            except RuntimeError as exc:
                chart_note = f"雷达图未生成：{exc} 报告保留表格版本。"
        env = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined, autoescape=False)
        rendered = env.get_template("report.md.j2").render(**data, chart_path=chart_path, chart_note=chart_note)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered.rstrip() + "\n", encoding="utf-8")
        print(f"REPORT: {args.output}")
        if chart_path: print(f"PNG: {chart_file}")
        else: print(chart_note)
        return 0
    except (OSError, json.JSONDecodeError, KeyError, ValueError, ImportError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())

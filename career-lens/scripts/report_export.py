"""HTML evidence and optional three-part PDF export from the same diagnosis."""
from pathlib import Path
from html import escape
import re
from urllib.parse import urlsplit

def evidence_html(markdown_text, title):
    import markdown
    body = markdown.markdown(escape(markdown_text), extensions=["tables"])
    def safe_href(match):
        url = match.group(1)
        return match.group(0) if urlsplit(url).scheme in ("", "http", "https") else 'href="#"'
    body = re.sub(r'href="([^"]*)"', safe_href, body)
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>body{{max-width:900px;margin:24px auto;padding:24px;color:#183149;font:16px/1.8 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}}h1{{font-size:26px}}h2{{margin-top:36px;font-size:23px}}h3{{font-size:19px}}a{{color:#1e5a9e;overflow-wrap:anywhere}}p,li{{overflow-wrap:anywhere}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:8px;border:1px solid #dde5ee}}</style><body>{body}</body></html>'''

def chart_flowable(chart_file, width=270):
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image
    source_width,source_height=ImageReader(str(chart_file)).getSize()
    return Image(str(chart_file),width=width,height=width*source_height/source_width)

def export_pdf(data, output, chart_file, evidence_file):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether
    from render_radar import find_chinese_font
    candidates = [find_chinese_font(), "/System/Library/Fonts/STHeiti Medium.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for path in candidates:
        if not path or not Path(path).is_file(): continue
        try:
            pdfmetrics.registerFont(TTFont("CareerCJK", path, subfontIndex=0)); break
        except Exception: continue
    else: raise RuntimeError("PDF export needs an embeddable Chinese TrueType font.")
    font="CareerCJK"
    normal=ParagraphStyle("Body",fontName=font,fontSize=10.5,leading=16,textColor=colors.HexColor("#183149"),wordWrap="CJK",spaceAfter=8)
    small=ParagraphStyle("Note",parent=normal,fontSize=8.5,leading=12,textColor=colors.HexColor("#536577"))
    heading=ParagraphStyle("Heading",parent=normal,fontSize=19,leading=28,spaceAfter=16)
    sub=ParagraphStyle("Sub",parent=normal,fontSize=12.5,leading=19,spaceBefore=9,spaceAfter=6)
    hero=ParagraphStyle("Hero",parent=normal,fontSize=14,leading=22,spaceAfter=12)
    story=[]; c=data["report_content"]; source_map={s["id"]:s for s in data["sources"]}
    def p(text,style=normal): return Paragraph(escape(text).replace("\n","<br/>"),style)
    def links(ids):
        chunks=[]
        for sid in ids:
            s=source_map[sid]
            chunks.append(f'<link href="{escape(s["url"],quote=True)}" color="#1e5a9e">{escape(s["organization"])}</link>' if s["url"] else escape(s["organization"]))
        return Paragraph("依据："+" · ".join(chunks),small)
    target=data["intake"]["target"]
    story += [p("CAREER LENS",small),p(target["sub_role"],heading),p(f'{target["location"]} · {target["seniority"]} · {target["as_of"]}',small)]
    if data.get("synthetic"): story.append(p("合成演示：岗位、个人经历与分数为虚构。",small))
    story.append(p(c["headline"],hero))
    if chart_file:
        image=chart_flowable(chart_file)
        story += [image,Spacer(1,5)]
    story += [p(c["scope_summary"],small),Spacer(1,6)]
    for f in c["findings"]:
        story.append(KeepTogether([p(f["title"],sub),p(f["text"]),links(f["source_ids"])]))
    story += [PageBreak(),p("02 / 最值得关注的差异" if data["candidate_evidence"]["materials"] else "02 / 核心任务与责任",heading)]
    for d in c["differences"]:
        story.append(KeepTogether([p(d["title"],sub),p("岗位任务："+d["market_requirement"]),p(("你的经历：" if data["candidate_evidence"]["materials"] else "材料范围：")+d["personal_evidence"]),p(("对你的影响：" if data["candidate_evidence"]["materials"] else "理解与应用：")+d["implication"]),links(d["source_ids"]),Spacer(1,12)]))
    story += [PageBreak(),p(f'03 / 接下来先做这{len(c["actions"])}件事',heading)]
    for i,a in enumerate(c["actions"],1):
        story.append(KeepTogether([p(f'{i}. {a["why"]}',sub),p("任务："+a["task"]),p("产出："+a["deliverable"]),p("完成条件："+a["check"]),p("顺序与周期："+a["period"]),Spacer(1,18)]))
    story.append(Paragraph(f'<link href="{escape(evidence_file.name)}" color="#1e5a9e">查看研究与判断依据（同目录文件）</link>',small))
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=34,bottomMargin=34,title="Career Lens职业诊断",author="Career Lens")
    def footer(canvas,doc):
        canvas.saveState(); canvas.setFont(font,8); canvas.setFillColor(colors.HexColor("#536577"))
        canvas.drawString(42,19,"Career Lens · 行为证据与岗位参照")
        canvas.drawRightString(A4[0]-42,19,str(doc.page)); canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)

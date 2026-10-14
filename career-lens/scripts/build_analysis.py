"""Export an authored, explanatory Markdown report without rating constraints.

The source is trusted local prose authored/reviewed by the host agent. Raw HTML
is allowed for deliberate diagrams; never render untrusted JD HTML as source.
Usage: python build_analysis.py report.md report.html
"""
import argparse
from pathlib import Path
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape


def build(source, output):
    raw = source.read_text(encoding='utf-8')
    body = markdown.markdown(raw, extensions=['tables', 'fenced_code', 'toc', 'md_in_html'],
                             extension_configs={'toc': {'permalink': False, 'toc_depth': '2-2'}})
    env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'templates'), autoescape=select_autoescape())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(env.get_template('analysis.html.j2').render(body=body), encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(build(args.source, args.output))

"""Validate linked, authored judgments and render a local reading page.

The host agent supplies all reasoning. Validation proves structure and references,
not that evidence entails a conclusion. Text is escaped by Jinja; no raw JD HTML.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader
from jsonschema import Draft202012Validator
from radar_contract import validate_radar

ROOT = Path(__file__).resolve().parents[1]
TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
REFS = {"type": "array", "items": TEXT, "minItems": 1, "uniqueItems": True}
OPTIONAL_REFS = {"type": "array", "items": TEXT, "uniqueItems": True}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": required or list(properties)}


def items(properties):
    return {"type": "array", "minItems": 1, "items": obj(properties)}


CASE_SCHEMA = obj({
    "case_id": TEXT, "revision": {"type": "integer", "minimum": 1},
    "kind": {"enum": ["personal", "synthetic"]}, "date": TEXT,
    "target": obj({"label": TEXT, "precision": {"enum": ["family", "direction", "posting"]},
                   "applicability": TEXT}),
    "knowledge": obj({"id": TEXT, "version": TEXT}),
    "evidence": items({"id": TEXT, "kind": {"enum": ["personal", "target"]},
                       "title": TEXT, "text": TEXT, "locator": TEXT}),
    "judgments": items({"id": TEXT, "statement": TEXT, "scope": TEXT,
                        "finding_kind": {"enum": ["strength", "experience_gap", "evidence_gap", "target_mismatch", "mixed"]},
                        "responsibility_refs": REFS, "evidence_refs": REFS,
                        "rationale": TEXT, "alternatives": REFS, "change_conditions": REFS}),
    "presentation": obj({"title": TEXT, "main_judgment": TEXT, "intro": TEXT,
                         "role_intro": TEXT, "responsibility_refs": REFS, "personal_intro": TEXT,
                         "comparison": items({"responsibility_ref": TEXT, "experience": TEXT,
                                              "difference": TEXT, "judgment_ref": TEXT}),
                         "paths": items({"title": TEXT, "fit": TEXT, "investment": TEXT,
                                        "tradeoff": TEXT, "choose_when": TEXT, "judgment_refs": REFS}),
                         "choice_note": TEXT})
})
KNOWLEDGE_SCHEMA = obj({
    "id": TEXT, "version": TEXT, "scope": TEXT,
    "maturity": {"enum": ["limited", "reviewed"]}, "limitations": TEXT,
    "sources": items({"id": TEXT, "title": TEXT, "url": TEXT, "captured_at": TEXT,
                      "visibility": {"enum": ["full_description", "partial_description"]},
                      "locator": TEXT, "summary": TEXT}),
    "responsibilities": items({"id": TEXT, "title": TEXT, "question": TEXT,
                               "observed": TEXT, "mechanism": TEXT, "evidence_standard": TEXT,
                               "scope": TEXT, "source_refs": REFS})
})

# Optional reading layer: the original V5 input remains valid.
CASE_SCHEMA['properties']['presentation']['properties']['reader'] = obj({
    'updated_at': TEXT,
    'snapshot': items({'label': TEXT, 'text': TEXT, 'judgment_refs': REFS}),
    'market_intro': TEXT,
    'conditions': items({'title': TEXT, 'requirement': TEXT, 'meaning': TEXT, 'check': TEXT,
                         'source_refs': OPTIONAL_REFS, 'evidence_refs': OPTIONAL_REFS,
                         'judgment_refs': REFS}),
    'insight': obj({'title': TEXT, 'text': TEXT, 'judgment_refs': REFS}),
    'findings': items({'status': {'enum': ['strength', 'expression', 'experience', 'target']},
                      'title': TEXT, 'fact': TEXT, 'meaning': TEXT, 'next': TEXT,
                      'judgment_refs': REFS}),
    'path_steps': {'type': 'array', 'items': TEXT},
    'next_step': obj({'title': TEXT, 'text': TEXT, 'judgment_refs': REFS})
})
# Connected explanation remains optional; older reading pages need no migration.
CASE_SCHEMA['properties']['presentation']['properties']['reader']['properties']['insight']['properties']['paragraphs'] = {
    'type': 'array', 'minItems': 1, 'items': TEXT
}
CASE_SCHEMA['properties']['presentation']['properties']['focus'] = obj({
    'summary': obj({'text': TEXT, 'judgment_refs': REFS}),
    'research_note': TEXT,
    'priorities': {'type': 'array', 'minItems': 1, 'maxItems': 2,
                   'items': obj({'title': TEXT, 'text': TEXT, 'judgment_refs': REFS})}
})


def validate(case, knowledge, previous=None):
    errors = []
    for label, document, schema in [("case", case, CASE_SCHEMA), ("knowledge", knowledge, KNOWLEDGE_SCHEMA)]:
        errors += [f"{label}.{'.'.join(map(str, e.path))}: {e.message}"
                   for e in Draft202012Validator(schema).iter_errors(document)]
    if errors:
        return errors

    def index(values, label):
        ids = [v['id'] for v in values]
        if len(ids) != len(set(ids)):
            errors.append(f"Duplicate {label} id")
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', i) for i in ids):
            errors.append(f"Unsafe {label} id")
        return {v['id']: v for v in values}

    sources = index(knowledge['sources'], 'source')
    tasks = index(knowledge['responsibilities'], 'responsibility')
    evidence = index(case['evidence'], 'evidence')
    judgments = index(case['judgments'], 'judgment')
    if case['knowledge'] != {'id': knowledge['id'], 'version': knowledge['version']}:
        errors.append('Knowledge id/version mismatch')
    for s in sources.values():
        u = urlparse(s['url'])
        if u.scheme != 'https' or not u.netloc:
            errors.append(f"{s['id']}: source URL must be HTTPS")
    for t in tasks.values():
        if set(t['source_refs']) - sources.keys():
            errors.append(f"{t['id']}: unknown source reference")
    for j in judgments.values():
        if set(j['responsibility_refs']) - tasks.keys():
            errors.append(f"{j['id']}: unknown responsibility reference")
        if set(j['evidence_refs']) - evidence.keys():
            errors.append(f"{j['id']}: unknown evidence reference")
        elif not any(evidence[e]['kind'] == 'personal' for e in j['evidence_refs']):
            errors.append(f"{j['id']}: personal judgment needs personal evidence")
    p = case['presentation']
    if p.get('radar') is not None:
        errors += validate_radar(p['radar'], tasks, sources, evidence, judgments)
    focus = p.get('focus')
    if focus:
        if not p.get('radar'):
            errors.append('Focused report needs a radar')
        elif not any(e.startswith('radar.') for e in errors):
            for axis in p['radar']['axes']:
                if not axis.get('explanation'):
                    errors.append(f"{axis['id']}: focused report needs an axis explanation")
        for item in [focus['summary'], *focus['priorities']]:
            if set(item['judgment_refs']) - judgments.keys():
                errors.append('Unknown focused-report judgment reference')
    if p['main_judgment'] not in judgments:
        errors.append('Unknown main judgment')
    if set(p['responsibility_refs']) - tasks.keys():
        errors.append('Unknown role presentation reference')
    for row in p['comparison']:
        t, j = row['responsibility_ref'], row['judgment_ref']
        if t not in tasks or j not in judgments:
            errors.append('Unknown comparison reference')
        elif t not in judgments[j]['responsibility_refs']:
            errors.append('Comparison responsibility absent from cited judgment')
    for path in p['paths']:
        if set(path['judgment_refs']) - judgments.keys():
            errors.append('Unknown path judgment reference')
    reader = p.get('reader')
    if reader:
        linked = reader['snapshot'] + reader['conditions'] + reader['findings'] + [reader['insight'], reader['next_step']]
        for item in linked:
            if set(item['judgment_refs']) - judgments.keys():
                errors.append('Unknown reading-layer judgment reference')
        for condition in reader['conditions']:
            if set(condition['source_refs']) - sources.keys():
                errors.append('Unknown condition source reference')
            if set(condition['evidence_refs']) - evidence.keys():
                errors.append('Unknown condition evidence reference')
            elif any(evidence[e]['kind'] != 'target' for e in condition['evidence_refs']):
                errors.append('Job conditions need target evidence, not personal facts')
            if not condition['source_refs'] and not condition['evidence_refs']:
                errors.append('Job condition needs a recruitment source or target JD')
        if len(reader['path_steps']) != len(p['paths']):
            errors.append('Path steps must correspond to paths')
    if case['target']['precision'] == 'posting' and not any(e['kind'] == 'target' for e in evidence.values()):
        errors.append('Posting analysis needs target JD evidence')
    if previous is not None:
        # Revisions are checked against a valid record, without inventing a new diagnosis.
        old_errors = validate(previous, knowledge)
        if old_errors:
            errors.append('Previous record invalid or uses a different knowledge version')
        else:
            if previous['case_id'] != case['case_id'] or case['revision'] <= previous['revision']:
                errors.append('Revision must preserve case id and increase revision')
            revision = case.get('revision_note', {})
            changed = {e['id'] for e in case['evidence'] if e not in previous['evidence']}
            actual = {j['id'] for j in case['judgments'] if j not in previous['judgments']}
            if not (changed or actual) or not revision.get('reason'):
                errors.append('Revision needs changed evidence or judgments and a reason')
            if not set(revision.get('changed_evidence_ids', [])) <= changed or (changed and not revision.get('changed_evidence_ids')):
                errors.append('Revision evidence ids must identify actual changes')
            if not revision.get('changed_judgment_ids') or not set(revision['changed_judgment_ids']) <= actual:
                errors.append('Revision judgment ids must identify actual changes')
    return errors


def build(case, knowledge, output, previous=None):
    errors = validate(case, knowledge, previous)
    if errors:
        raise ValueError('\n'.join(errors))
    # The template suffix is .html.j2, which select_autoescape does not recognize.
    env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=True)
    data = dict(case=case, knowledge=knowledge, p=case['presentation'],
                reader=case['presentation'].get('reader'),
                radar=case['presentation'].get('radar'),
                focus=case['presentation'].get('focus'),
                judgments={j['id']: j for j in case['judgments']},
                evidence={e['id']: e for e in case['evidence']},
                tasks={r['id']: r for r in knowledge['responsibilities']},
                sources={s['id']: s for s in knowledge['sources']},
                css=(ROOT / 'templates' / 'decision.css').read_text(),
                radar_js=(ROOT / 'templates' / 'radar.js').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(env.get_template('decision.html.j2').render(**data), encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('case', 'knowledge', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    try:
        documents = [json.loads(p.read_text()) for p in (args.case, args.knowledge)]
        previous = json.loads(args.previous.read_text()) if args.previous else None
        print(build(*documents, args.output, previous))
    except (ValueError, OSError) as error:
        parser.exit(2, f'Cannot build reading page: {error}\n')


if __name__ == '__main__':
    main()

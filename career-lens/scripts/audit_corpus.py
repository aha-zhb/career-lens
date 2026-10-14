"""Audit research bookkeeping, not the truth of a role interpretation.

Usage: python audit_corpus.py corpus.json [--output audit.json]
Paths in corpus.json are relative to that file. Exit 2 means invalid input;
an honest limited corpus exits 0 and reports deep_release_pass=false.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path


def audit(data, base, today=None):
    today = today or date.today()
    errors = []
    records = data.get('records', [])
    ids = [r.get('id') for r in records]
    if len(ids) != len(set(ids)) or None in ids:
        errors.append('Each record needs a unique id')
    accepted = []
    for r in records:
        if r.get('decision') not in {'target', 'benchmark', 'exclude', 'unreviewed'}:
            errors.append(f"{r.get('id')}: invalid decision")
        if r.get('visibility') not in {'full_description', 'partial_description', 'unreadable'}:
            errors.append(f"{r.get('id')}: invalid visibility")
        if r.get('decision') != 'target':
            continue
        required = ('url', 'employer', 'template_id', 'origin_channel',
                    'business_group', 'scope_reason', 'body_file', 'collected_at')
        if any(not r.get(k) for k in required):
            errors.append(f"{r.get('id')}: missing target provenance")
            continue
        body = (base / r['body_file']).resolve()
        if not body.is_relative_to(base.resolve()):
            errors.append(f"{r['id']}: body path escapes corpus directory")
            continue
        if not body.is_file():
            errors.append(f"{r['id']}: body file missing")
            continue
        digest = hashlib.sha256(body.read_bytes()).hexdigest()
        if r.get('body_sha256') != digest:
            errors.append(f"{r['id']}: body hash mismatch")
            continue
        text = body.read_text(encoding='utf-8')
        for marker, origin in [('来源于猎聘', 'liepin'), ('来源于智联', 'zhaopin')]:
            if marker in text and r['origin_channel'] != origin:
                errors.append(f"{r['id']}: mirror origin contradicts captured body")
        if r['origin_channel'] not in {'official', 'liepin', 'zhaopin', 'linkedin', 'zhipin', '51job', 'lagou', 'public_employer_announcement'}:
            errors.append(f"{r['id']}: unrecognized origin channel")
        if r.get('visibility') != 'full_description':
            continue
        try:
            age = (today - date.fromisoformat(r['collected_at'])).days
            if age < 0 or age > 30:
                continue
            if r.get('published_at'):
                if date.fromisoformat(r['published_at']) > today:
                    errors.append(f"{r['id']}: future publication date")
        except ValueError:
            errors.append(f"{r['id']}: invalid date")
            continue
        if r.get('unknown_employer'):
            continue
        accepted.append(r)
    groups = {}
    for r in accepted:
        groups.setdefault(r['template_id'], []).append(r)
    for key, copies in groups.items():
        if len({r['employer'] for r in copies}) > 1:
            errors.append(f'{key}: template group crosses employers; review grouping')
    # A mirror is one template; prefer its named original channel. Do not credit
    # LinkedIn as independent sourcing when the record identifies a Liepin origin.
    unique = [copies[0] for copies in groups.values()]
    channels = Counter(r['origin_channel'] for r in unique)
    employers = {r['employer'] for r in unique}
    sectors = Counter(r['business_group'] for r in unique)
    train = {r['employer'] for r in accepted if r.get('split') == 'train'}
    holdout = {r['employer'] for r in accepted if r.get('split') == 'holdout'}
    if train & holdout:
        errors.append('Employer leakage between train and holdout')
    review = data.get('synthesis_review', {})
    gates = {
        'templates_60': len(unique) >= 60,
        'employers_25': len(employers) >= 25,
        'channels_4': len(channels) >= 4,
        'official_present': channels['official'] > 0,
        'recruitment_platforms_2': len(set(channels) & {'liepin', 'zhaopin', 'linkedin', 'zhipin', '51job', 'lagou'}) >= 2,
        'largest_channel_at_most_half': bool(unique) and max(channels.values(), default=0) / len(unique) <= .5,
        'business_groups_3': len(sectors) >= 3,
        'prospective_holdout_review': bool(unique) and .15 <= sum(r.get('split') == 'holdout' for r in unique) / len(unique) <= .3 and review.get('holdout_reserved_before_model') is True and review.get('holdout_review_completed') is True,
        'task_matrix_and_counterexamples': review.get('task_matrix_completed') is True and review.get('counterexamples_reviewed') is True,
        'two_stable_incremental_batches': review.get('two_stable_batches_completed') is True,
        'coverage_review': review.get('coverage_approved') is True,
    }
    return {
        'audited_at': today.isoformat(), 'errors': errors,
        'registered_pages': len({r.get('url') for r in records if r.get('url')}),
        'reviewed_description_pages': sum(r.get('decision') != 'unreviewed' and r.get('visibility') in {'full_description', 'partial_description'} for r in records),
        'target_description_pages': sum(r.get('decision') == 'target' for r in records),
        'fresh_full_independent_target_templates': len(unique),
        'known_employers': len(employers), 'origin_channels': dict(channels),
        'business_groups': dict(sectors),
        'publication_date_unknown_templates': sum(not r.get('published_at') for r in unique),
        'gates': gates, 'deep_release_pass': not errors and all(gates.values()),
        'interpretation': 'Counts audit registered, agent-reviewed records only; they do not certify semantic coding, market representativeness, or reader understanding.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.corpus.read_text()), args.corpus.parent)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n')
    print(text)
    raise SystemExit(2 if result['errors'] else 0)


if __name__ == '__main__':
    main()

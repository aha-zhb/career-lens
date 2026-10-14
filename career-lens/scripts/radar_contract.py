"""Reference checks for a scoped, evidence-linked radar; no automatic scoring."""
from jsonschema import Draft202012Validator

TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
REFS = {'type': 'array', 'items': TEXT, 'minItems': 1, 'uniqueItems': True}
OPTIONAL_REFS = {'type': 'array', 'items': TEXT, 'uniqueItems': True}
LEVEL = {'type': 'integer', 'minimum': 1, 'maximum': 5}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties)}


SCHEMA = obj({
    'title': TEXT, 'scope': TEXT, 'description': TEXT, 'default_axis': TEXT,
    'scale_id': {'const': 'task-responsibility-5-v1'},
    'axes': {'type': 'array', 'minItems': 3, 'maxItems': 8, 'items': obj({
        'id': {'type': 'string', 'pattern': r'^[A-Za-z][A-Za-z0-9_-]*$'},
        'label': TEXT, 'label_lines': {'type': 'array', 'items': TEXT, 'minItems': 1, 'maxItems': 2},
        'task_ref': TEXT,
        'anchors': {'type': 'array', 'items': TEXT, 'minItems': 5, 'maxItems': 5},
        'required_level': LEVEL, 'personal_level': {'anyOf': [LEVEL, {'type': 'null'}]},
        'status': {'enum': ['demonstrated', 'information_gap', 'experience_gap']},
        'basis': {'enum': ['observed', 'inferred', 'unrated']},
        'required_reason': TEXT, 'personal_reason': TEXT, 'gap_note': TEXT,
        'source_refs': OPTIONAL_REFS, 'target_evidence_refs': OPTIONAL_REFS,
        'personal_evidence_refs': REFS, 'judgment_refs': REFS
    })}
})
# Plain-language text shares the axis references and never changes its score.
SCHEMA['properties']['axes']['items']['properties']['explanation'] = obj({
    'requirement': TEXT, 'experience': TEXT, 'difference': TEXT
})


def validate_radar(radar, tasks, sources, evidence, judgments):
    errors = [f"radar.{'.'.join(map(str, e.path))}: {e.message}"
              for e in Draft202012Validator(SCHEMA).iter_errors(radar)]
    if errors:
        return errors
    ids = [a['id'] for a in radar['axes']]
    if len(ids) != len(set(ids)):
        errors.append('Duplicate radar axis id')
    if radar['default_axis'] not in ids:
        errors.append('Unknown default radar axis')
    for axis in radar['axes']:
        label = axis['id']
        for field, index in [('source_refs', sources), ('target_evidence_refs', evidence),
                             ('personal_evidence_refs', evidence), ('judgment_refs', judgments)]:
            if set(axis[field]) - index.keys():
                errors.append(f'{label}: unknown {field}')
        if axis['task_ref'] not in tasks:
            errors.append(f'{label}: unknown radar task')
        elif all(j not in judgments or axis['task_ref'] not in judgments[j]['responsibility_refs']
                 for j in axis['judgment_refs']):
            errors.append(f'{label}: radar task not supported by cited judgment')
        if not axis['source_refs'] and not axis['target_evidence_refs']:
            errors.append(f'{label}: target level needs recruitment evidence')
        for ref in axis['personal_evidence_refs']:
            if ref in evidence and evidence[ref]['kind'] != 'personal':
                errors.append(f'{label}: personal level cannot use target JD')
        for ref in axis['target_evidence_refs']:
            if ref in evidence and evidence[ref]['kind'] != 'target':
                errors.append(f'{label}: target level cannot use personal evidence')
        if axis['personal_level'] is None:
            if axis['status'] == 'demonstrated' or axis['basis'] != 'unrated':
                errors.append(f'{label}: null must have an unscored gap explanation')
        elif axis['status'] != 'demonstrated' or axis['basis'] == 'unrated':
            errors.append(f'{label}: numeric level must describe demonstrated work')
    return errors

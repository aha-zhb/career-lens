import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_decision import build, validate


def load(path):
    return json.loads(path.read_text())


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.knowledge = load(ROOT / 'knowledge/enterprise-ai-applications.json')
        self.case = load(ROOT / 'examples/v05/01-experience-gap.json')

    def add_focus(self):
        self.case['presentation']['focus'] = {
            'summary': {'text': 'Overall judgment', 'judgment_refs': ['J1']},
            'research_note': 'Archived research scope',
            'priorities': [{'title': 'Priority', 'text': 'Reason', 'judgment_refs': ['J1']}]}
        for axis in self.case['presentation']['radar']['axes']:
            axis['explanation'] = {'requirement': 'Why the work matters',
                                   'experience': 'Related personal work',
                                   'difference': 'A concrete difference'}

    def test_all_examples_have_resolvable_judgments(self):
        for path in (ROOT / 'examples/v05').glob('*.json'):
            with self.subTest(path=path.name):
                self.assertEqual(validate(load(path), self.knowledge), [])

    def test_unknown_and_duplicate_evidence_fail(self):
        self.case['judgments'][0]['evidence_refs'].append('NONEXISTENT')
        self.assertTrue(any('unknown evidence' in e for e in validate(self.case, self.knowledge)))
        self.case['evidence'].append(self.case['evidence'][0])
        self.assertTrue(any('Duplicate evidence' in e for e in validate(self.case, self.knowledge)))

    def test_unknown_role_source_fails(self):
        self.knowledge['responsibilities'][0]['source_refs'] = ['NONEXISTENT']
        self.assertTrue(any('unknown source' in e for e in validate(self.case, self.knowledge)))

    def test_knowledge_version_mismatch_fails(self):
        self.case['knowledge']['version'] = 'other-version'
        self.assertIn('Knowledge id/version mismatch', validate(self.case, self.knowledge))

    def test_posting_requires_supplied_jd(self):
        self.case['evidence'] = [e for e in self.case['evidence'] if e['kind'] == 'personal']
        self.assertIn('Posting analysis needs target JD evidence', validate(self.case, self.knowledge))

    def test_target_evidence_alone_cannot_establish_personal_judgment(self):
        self.case['judgments'][0]['evidence_refs'] = ['T1']
        self.assertTrue(any('needs personal evidence' in e for e in validate(self.case, self.knowledge)))

    def test_comparison_cannot_cite_unrelated_judgment(self):
        self.case['presentation']['comparison'][0]['responsibility_ref'] = 'D5'
        self.assertIn('Comparison responsibility absent from cited judgment', validate(self.case, self.knowledge))

    def test_unsafe_source_url_and_anchor_fail(self):
        self.knowledge['sources'][0]['url'] = 'javascript:alert(1)'
        self.case['evidence'][0]['id'] = 'bad"id'
        errors = validate(self.case, self.knowledge)
        self.assertTrue(any('HTTPS' in e for e in errors))
        self.assertIn('Unsafe evidence id', errors)

    def test_empty_reasoning_fails_before_render(self):
        self.case['judgments'][0]['rationale'] = '  '
        self.assertTrue(validate(self.case, self.knowledge))

    def test_revision_requires_real_material_changes_and_identified_judgments(self):
        revised = load(ROOT / 'examples/v05/01-experience-gap-revised.json')
        self.assertEqual(validate(revised, self.knowledge, self.case), [])
        revised['revision_note']['changed_evidence_ids'] = ['E1']
        self.assertTrue(any('actual changes' in e for e in validate(revised, self.knowledge, self.case)))

    def test_cosmetic_revision_without_new_evidence_fails(self):
        revised = copy.deepcopy(self.case)
        revised['revision'] += 1
        revised['presentation']['title'] = '换一个标题'
        self.assertTrue(any('changed evidence' in e for e in validate(revised, self.knowledge, self.case)))

    def test_reasoned_revision_can_reinterpret_existing_evidence(self):
        revised = copy.deepcopy(self.case)
        revised['revision'] += 1
        revised['judgments'][0]['rationale'] += ' Existing work can be interpreted without claiming new facts.'
        revised['revision_note'] = {'reason': 'Reinterpret existing material',
                                    'changed_evidence_ids': [], 'changed_judgment_ids': ['J1']}
        self.assertEqual(validate(revised, self.knowledge, self.case), [])
        revised['revision_note']['changed_judgment_ids'] = ['J2']
        self.assertTrue(any('actual changes' in e for e in validate(revised, self.knowledge, self.case)))
        revised['revision_note']['changed_judgment_ids'] = ['J1']
        revised['revision_note'].pop('reason')
        self.assertTrue(any('a reason' in e for e in validate(revised, self.knowledge, self.case)))

    def test_explanatory_paragraphs_are_validated_and_escaped(self):
        insight = self.case['presentation']['reader']['insight']
        insight['paragraphs'] = ['First explanation <script>alert(1)</script>', 'Second explanation']
        self.assertEqual(validate(self.case, self.knowledge), [])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            build(self.case, self.knowledge, output)
            html = output.read_text()
        self.assertIn('First explanation &lt;script&gt;', html)
        self.assertNotIn('First explanation <script>', html)
        self.assertLess(html.index('First explanation'), html.index('Second explanation'))
        insight['paragraphs'] = ['  ']
        self.assertTrue(validate(self.case, self.knowledge))

    def test_invalid_previous_record_does_not_crash(self):
        self.assertTrue(validate(self.case, self.knowledge, {'case_id': 'broken'}))

    def test_main_statement_is_rendered_from_same_record_and_untrusted_text_escaped(self):
        self.case['judgments'][0]['statement'] = '可追溯结论 <script>alert(1)</script>'
        self.case['evidence'][0]['text'] = '<img src=x onerror=alert(1)>'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            build(self.case, self.knowledge, output)
            html = output.read_text()
        self.assertEqual(html.count('可追溯结论 &lt;script&gt;'), 2)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;img src=x', html)
        self.assertIn('虚构案例', html)

    def test_invalid_record_cannot_overwrite_output(self):
        self.case['presentation']['main_judgment'] = 'MISSING'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            output.write_text('existing review')
            with self.assertRaises(ValueError):
                build(self.case, self.knowledge, output)
            self.assertEqual(output.read_text(), 'existing review')

    def test_reading_conditions_require_recruitment_evidence(self):
        condition = self.case['presentation']['reader']['conditions'][0]
        condition['source_refs'] = []
        condition['evidence_refs'] = []
        self.assertIn('Job condition needs a recruitment source or target JD', validate(self.case, self.knowledge))
        condition['evidence_refs'] = ['E1']
        self.assertIn('Job conditions need target evidence, not personal facts', validate(self.case, self.knowledge))

    def test_reading_condition_and_snapshot_references_are_checked(self):
        r = self.case['presentation']['reader']
        r['conditions'][0]['source_refs'] = ['MISSING']
        r['snapshot'][0]['judgment_refs'] = ['MISSING']
        errors = validate(self.case, self.knowledge)
        self.assertIn('Unknown condition source reference', errors)
        self.assertIn('Unknown reading-layer judgment reference', errors)

    def test_path_steps_cannot_drift_from_paths(self):
        self.case['presentation']['reader']['path_steps'].pop()
        self.assertIn('Path steps must correspond to paths', validate(self.case, self.knowledge))

    def test_original_v5_contract_still_renders(self):
        self.case['presentation'].pop('reader')
        self.case['presentation'].pop('radar', None)
        self.assertEqual(validate(self.case, self.knowledge), [])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            build(self.case, self.knowledge, output)
            html = output.read_text()
        self.assertIn('role="table"', html)
        self.assertIn('href="#role"', html)
        self.assertNotIn('href="#market"', html)

    def test_focus_needs_complete_explanations_and_supported_references(self):
        self.add_focus()
        self.assertEqual(validate(self.case, self.knowledge), [])
        axis = self.case['presentation']['radar']['axes'][0]
        axis.pop('explanation')
        self.assertTrue(any('axis explanation' in e for e in validate(self.case, self.knowledge)))
        self.case['presentation']['focus']['summary']['judgment_refs'] = ['MISSING']
        self.assertIn('Unknown focused-report judgment reference', validate(self.case, self.knowledge))
        self.case['presentation'].pop('radar')
        self.assertIn('Focused report needs a radar', validate(self.case, self.knowledge))

    def test_focus_limits_priorities_and_rejects_blank_explanation(self):
        self.add_focus()
        focus = self.case['presentation']['focus']
        focus['priorities'] *= 3
        self.assertTrue(validate(self.case, self.knowledge))
        focus['priorities'] = focus['priorities'][:1]
        self.case['presentation']['radar']['axes'][0]['explanation']['difference'] = '  '
        self.assertTrue(validate(self.case, self.knowledge))

    def test_focus_renders_axis_text_safely_without_old_main_chapters(self):
        self.add_focus()
        self.case['presentation']['radar']['axes'][0]['explanation']['requirement'] = '<script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            build(self.case, self.knowledge, output)
            html = output.read_text()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('class="focus-report"', html)
        self.assertIn('id="dimensions"', html)
        self.assertNotIn('id="market"', html)
        self.assertNotIn('id="personal"', html)
        self.assertNotIn('id="paths"', html)
        self.assertIn('id="reasoning"', html)

    def test_focus_can_use_another_occupation_and_three_dimensions(self):
        example = load(ROOT / 'examples/focused-customer-success.json')
        self.assertEqual(validate(example['case'], example['knowledge']), [])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            build(example['case'], example['knowledge'], output)
            html = output.read_text()
        self.assertEqual(html.count('data-axis-card='), 3)
        self.assertIn('续约', html)
        self.assertNotIn('AI方案设计', html)

    def test_radar_rejects_zero_and_inconsistent_missingness(self):
        axis = self.case['presentation']['radar']['axes'][0]
        axis['personal_level'] = 0
        self.assertTrue(validate(self.case, self.knowledge))
        axis['personal_level'] = None
        self.assertTrue(any('null must' in e for e in validate(self.case, self.knowledge)))

    def test_radar_personal_levels_cannot_use_jd_evidence(self):
        axis = self.case['presentation']['radar']['axes'][0]
        axis['personal_evidence_refs'] = ['T1']
        self.assertTrue(any('personal level cannot use target' in e for e in validate(self.case, self.knowledge)))

    def test_radar_requires_sources_and_shared_task(self):
        axis = self.case['presentation']['radar']['axes'][0]
        axis['source_refs'] = []
        axis['task_ref'] = 'D5'
        errors = validate(self.case, self.knowledge)
        self.assertTrue(any('needs recruitment' in e for e in errors))
        self.assertTrue(any('task not supported' in e for e in errors))

    def test_radar_rejects_unknown_or_duplicate_axis(self):
        r = self.case['presentation']['radar']
        r['default_axis'] = 'MISSING'
        r['axes'][1]['id'] = r['axes'][0]['id']
        errors = validate(self.case, self.knowledge)
        self.assertIn('Duplicate radar axis id', errors)
        self.assertIn('Unknown default radar axis', errors)

    def test_radar_data_cannot_escape_json_script(self):
        self.case['presentation']['radar']['axes'][0]['personal_reason'] = '</script><img src=x onerror=alert(1)>'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.html'
            build(self.case, self.knowledge, output)
            html = output.read_text()
        self.assertNotIn('</script><img src=x', html)
        self.assertIn('\\u003c/script\\u003e', html)

    def test_radar_target_level_is_not_boolean_or_out_of_range(self):
        axis = self.case['presentation']['radar']['axes'][0]
        for value in [True, 0, 6, 2.5]:
            axis['required_level'] = value
            self.assertTrue(validate(self.case, self.knowledge))


if __name__ == '__main__':
    unittest.main()

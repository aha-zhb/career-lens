import copy
from datetime import date
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_corpus import audit
from build_analysis import build


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.body = self.base / 'body.txt'
        self.body.write_text('Synthetic job body: independent enterprise task and requirements.')
        self.record = dict(id='A', url='https://example.test/job', employer='Fictional Co',
                           template_id='T1', origin_channel='official', business_group='enterprise',
                           scope_reason='Synthetic test fixture, not market evidence', body_file='body.txt',
                           body_sha256=hashlib.sha256(self.body.read_bytes()).hexdigest(),
                           collected_at='2026-10-11', published_at=None, visibility='full_description',
                           decision='target', split='train')

    def tearDown(self):
        self.tmp.cleanup()

    def run_audit(self, *records, review=None):
        return audit(dict(records=list(records), synthesis_review=review or {}), self.base, date(2026, 10, 11))

    def test_small_honest_corpus_valid_but_not_deep_release(self):
        r = self.run_audit(self.record)
        self.assertEqual(r['errors'], [])
        self.assertEqual(r['fresh_full_independent_target_templates'], 1)
        self.assertFalse(r['deep_release_pass'])

    def test_mirrors_deduplicate(self):
        b = {**self.record, 'id': 'B', 'url': 'https://example.test/mirror'}
        self.assertEqual(self.run_audit(self.record, b)['fresh_full_independent_target_templates'], 1)

    def test_partial_snippet_benchmark_and_unknown_employer_do_not_fill_quota(self):
        for change in [dict(visibility='partial_description'), dict(decision='benchmark'),
                       dict(decision='unreviewed'), dict(unknown_employer=True)]:
            with self.subTest(change=change):
                self.assertEqual(self.run_audit({**self.record, **change})['fresh_full_independent_target_templates'], 0)

    def test_fetch_date_not_publication_date(self):
        r = self.run_audit(self.record)
        self.assertEqual(r['publication_date_unknown_templates'], 1)

    def test_stale_capture_not_current_quota(self):
        r = self.run_audit({**self.record, 'collected_at': '2026-08-01'})
        self.assertEqual(r['fresh_full_independent_target_templates'], 0)

    def test_changed_or_missing_body_rejected(self):
        self.body.write_text('Different body')
        self.assertTrue(self.run_audit(self.record)['errors'])
        self.body.unlink()
        self.assertTrue(self.run_audit(self.record)['errors'])

    def test_company_leakage_even_with_duplicate_template(self):
        b = {**self.record, 'id': 'B', 'split': 'holdout'}
        self.assertIn('Employer leakage between train and holdout', self.run_audit(self.record, b)['errors'])

    def test_mirror_cannot_add_a_channel(self):
        self.body.write_text('该职位来源于猎聘。Synthetic task.')
        r = {**self.record, 'body_sha256': hashlib.sha256(self.body.read_bytes()).hexdigest(), 'origin_channel': 'linkedin'}
        self.assertTrue(any('mirror origin' in e for e in self.run_audit(r)['errors']))

    def test_future_publication_and_unknown_channel_rejected(self):
        self.assertTrue(self.run_audit({**self.record, 'published_at': '2027-01-01'})['errors'])
        self.assertTrue(self.run_audit({**self.record, 'origin_channel': 'another-mirror'})['errors'])

    def test_corpus_body_cannot_read_outside_its_directory(self):
        r=self.run_audit({**self.record, 'body_file':'../other-material.txt'})
        self.assertTrue(any('escapes' in e for e in r['errors']))

    def test_public_announcement_is_not_another_recruitment_platform(self):
        b={**self.record, 'id':'B', 'template_id':'T2', 'origin_channel':'public_employer_announcement'}
        c={**self.record, 'id':'C', 'template_id':'T3', 'origin_channel':'liepin'}
        self.assertFalse(self.run_audit(self.record,b,c)['gates']['recruitment_platforms_2'])

    def test_counts_cannot_substitute_for_reasoning_checks(self):
        records=[]
        for i in range(60):
            records.append({**self.record, 'id':str(i), 'template_id':str(i), 'employer':str(i),
                            'origin_channel':['official','liepin','zhaopin','linkedin'][i%4],
                            'business_group':str(i%3), 'split':'holdout' if i<12 else 'train'})
        r=self.run_audit(*records)
        self.assertTrue(r['gates']['templates_60'])
        self.assertFalse(r['deep_release_pass'])
        review={k:True for k in ['holdout_reserved_before_model','holdout_review_completed',
                                'task_matrix_completed','counterexamples_reviewed',
                                'two_stable_batches_completed','coverage_approved']}
        self.assertTrue(self.run_audit(*records, review=review)['deep_release_pass'])

    def test_long_prose_is_not_truncated_and_no_radar_required(self):
        source=self.base/'report.md';output=self.base/'report.html'
        source.write_text('# 示例\n\n'+'解释内容。'*900+'\n\n末尾建议\n\n|任务|材料|\n|---|---|\n|判断|案例|\n')
        build(source,output);html=output.read_text()
        self.assertIn('末尾建议',html);self.assertIn('<table>',html)
        self.assertNotIn('radar',html);self.assertIn('lang="zh-CN"',html)


if __name__ == '__main__':
    unittest.main()

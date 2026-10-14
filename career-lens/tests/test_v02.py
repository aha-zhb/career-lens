import copy,json,sys,tempfile,unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from validate_input import validate
from render_overview import adjacent_segments,choose_mode,chart_values,selected_dimensions
from normalize_jds import normalize
from build_report import build_v2
from report_export import evidence_html

def fixture():return json.loads((ROOT/'examples/synthetic-v02-case.json').read_text())
def unrate(d,ids):
 for dim in d['market_model']['dimensions']:
  if dim['id'] in ids:
   dim['market_level']=None;dim.pop('market_level_range',None);dim['rating_review']['approved']=False
 rated=any(x['market_level'] or x.get('market_level_range') for x in d['market_model']['dimensions'])
 d['market_model']['market_confidence']='mixed' if rated else 'exploratory_only';d['market_model']['quality_review']['approved_for_rating']=rated
class V02Tests(unittest.TestCase):
 def test_v02_fixture_passes_without_redundant_conclusions(self):
  d=fixture();self.assertNotIn('three_conclusions',d['report_content']);self.assertEqual(validate(d),[])
 def test_level_range_is_valid_and_not_a_midpoint(self):
  d=fixture();dm=d['market_model']['dimensions'][0];dm['market_level']=None;dm['market_level_range']=[3,4]
  self.assertEqual(validate(d),[]);self.assertEqual(chart_values(d)[1][0],[3,4])
 def test_reversed_or_duplicate_rating_rejected(self):
  for point,band in [(None,[4,3]),(3,[3,4])]:
   d=fixture();dm=d['market_model']['dimensions'][0];dm['market_level']=point;dm['market_level_range']=band
   self.assertTrue(validate(d))
 def test_verified_personal_range_requires_evidence(self):
  d=fixture();p=d['candidate_evidence']['assessments'][0];p['score']=None;p['score_range']=[3,4]
  self.assertEqual(validate(d),[]);p['evidence_ids']=[];self.assertTrue(validate(d))
 def test_unknown_range_is_rejected(self):
  d=fixture();p=d['candidate_evidence']['assessments'][0];p.update(score=None,status='unknown',score_range=[1,2])
  self.assertTrue(any('unknown requires null' in x for x in validate(d)))
 def test_no_legacy_range_without_version(self):
  d=fixture();d.pop('schema_version');d['report_content']['three_conclusions']=['a','b','c'];d['market_model']['dimensions'][0]['market_level_range']=[3,4]
  self.assertTrue(any('require V0.2' in x for x in validate(d)))
 def test_partial_market_does_not_erase_supported_axes(self):
  d=fixture();unrate(d,['value_iteration']);self.assertEqual(validate(d),[]);self.assertEqual(choose_mode(d),'radar')
  self.assertIsNone(chart_values(d)[1][-1]);self.assertEqual(chart_values(d)[1][0],[3,3])
 def test_selected_order_and_unselected_null_do_not_block(self):
  d=fixture();unrate(d,['value_iteration']);d['market_model']['radar_dimension_ids']=['delivery','evaluation','agent_design']
  self.assertEqual([x['id'] for x in selected_dimensions(d)],['delivery','evaluation','agent_design']);self.assertEqual(choose_mode(d),'radar')
 def test_per_dimension_approval_is_required(self):
  d=fixture();d['market_model']['dimensions'][0]['rating_review']['approved']=False
  self.assertTrue(any('own approved' in x for x in validate(d)))
 def test_practice_separate_from_job_counts(self):
  d=fixture();s=copy.deepcopy(d['sources'][0]);s.update(id='SYNTH-P1',source_kind='practice',source_layer='work_practice',role_track='other');d['sources'].append(s)
  self.assertEqual(validate(d),[]);d['market_model']['candidate_jd_count']=2;self.assertTrue(validate(d))
 def test_practice_alone_cannot_support_real_market_rating(self):
  d=fixture();d['synthetic']=False;d['case_id']='real-test';d['sources'][0].update(id='P1',source_kind='practice',source_layer='work_practice',role_track='other',source_status='active',url='https://www.anthropic.com/engineering/building-effective-agents');m=d['market_model'];m.update(candidate_jd_count=0,eligible_jd_count=0,sources=['P1'],sampling_method='test',sample_limitations=['方法测试'])
  for dm in m['dimensions']:dm['supporting_sources']=['P1']
  for t in m['capability_tree']:t['source_ids']=['P1']
  for r in m['research_rounds']:r['new_source_ids']=['P1']
  for f in d['report_content']['findings']+d['report_content']['differences']:f['source_ids']=['P1']
  d['intake']['provided_jd_ids']=[]
  self.assertTrue(any('practice alone is insufficient' in x for x in validate(d)))
 def test_search_summary_cannot_be_included(self):
  d=fixture();d['sources'][0]['body_access']='summary';self.assertTrue(any('reviewed body' in x for x in validate(d)))
 def test_role_benchmark_shared_application_allowed_but_platform_rejected(self):
  d=fixture();d['sources'][0].update(source_layer='role_benchmark',role_track='ai_application_pm',location='合成外地');self.assertEqual(validate(d),[])
  d['sources'][0]['role_track']='ai_platform_pm';self.assertTrue(any('does not match' in x for x in validate(d)))
 def test_local_geography_must_match(self):
  d=fixture();d['sources'][0]['location']='外地';self.assertTrue(any('geography' in x for x in validate(d)))
 def test_role_first_market_accepts_same_role_outside_preferred_city(self):
  d=fixture();d['market_model'].update(geography_mode='role_first',geography='全国同岗位');d['sources'][0]['location']='外地'
  self.assertEqual(validate(d),[])
 def test_role_first_does_not_mix_platform_into_application(self):
  d=fixture();d['market_model']['geography_mode']='role_first';d['sources'][0].update(location='外地',role_track='ai_platform_pm')
  self.assertTrue(any('does not match the target' in x for x in validate(d)))
 def test_explicit_location_first_keeps_local_study_constraint(self):
  d=fixture();d['market_model']['geography_mode']='location_first';d['sources'][0]['location']='外地'
  self.assertTrue(any('geography' in x for x in validate(d)))
 def test_tree_components_preserved(self):
  d=fixture();d['market_model']['capability_tree'].pop();self.assertTrue(any('components' in x for x in validate(d)))
 def test_findings_need_aligned_evidence(self):
  d=fixture();d['report_content']['findings'][0]['evidence_ids']=['SYNTH-E1'];self.assertTrue(any('support a linked capability' in x for x in validate(d)))
 def test_internal_pending_labels_rejected_in_main_narrative(self):
  d=fixture();d['report_content']['headline']='你的等级未决，请等待。';self.assertTrue(any('internal pending labels' in x for x in validate(d)))
 def test_personal_research_actions_not_passed_to_user(self):
  d=fixture();d['report_content']['actions'][0]['action_type']='market_research';self.assertTrue(any('belongs to the agent' in x for x in validate(d)))
 def test_no_segments_bridge_unknown_or_range_axes(self):
  self.assertEqual(adjacent_segments([[3,3],None,[2,2],[3,4]]),[])
  self.assertEqual(adjacent_segments([[3,3],[2,2],None,[3,3]]),[(0,1),(3,0)])
 def test_no_personal_scores_defaults_to_relation(self):
  d=fixture()
  for p in d['candidate_evidence']['assessments']:p.update(score=None,status='partial')
  self.assertEqual(validate(d),[]);self.assertEqual(choose_mode(d),'relation')
 def test_forced_radar_requires_selected_market_ratings(self):
  d=fixture();unrate(d,[x['id'] for x in d['market_model']['dimensions']]);d['report_content']['chart_mode']='radar'
  self.assertTrue(any('radar requires supported' in x for x in validate(d)))
 def test_source_script_scheme_rejected(self):
  d=fixture();d['sources'][0]['url']='javascript:alert(1)';self.assertTrue(any('http or https' in x for x in validate(d)))
 def test_normalizer_preserves_layer_and_body(self):
  s=fixture()['sources'][0];s.update(role_track='ai_application_pm',source_layer='role_benchmark');row=normalize([s],{'ai_agent_application_pm'})[0]
  self.assertEqual(row['eligibility'],'included');self.assertEqual(row['source_layer'],'role_benchmark');self.assertEqual(row['body_access'],'full')
 def test_normalizer_keeps_summary_leads_pending(self):
  s=fixture()['sources'][0];s['body_access']='summary';row=normalize([s])[0]
  self.assertEqual(row['eligibility'],'pending_review');self.assertEqual(validate([row],'jd.schema.json'),[])
 def test_companion_html_escapes_raw_html_and_unsafe_href(self):
  html=evidence_html('<script>alert(1)</script>\n\n[unsafe](javascript:alert)','test')
  self.assertNotIn('<script>',html);self.assertNotIn('href="javascript:',html)
 def test_market_only_output_never_implies_personal_assessment(self):
  d=fixture();d['candidate_evidence'].update(materials=[],evidence=[],assessments=[],events=[]);d['intake']['candidate_material_ids']=[]
  for f in d['report_content']['findings']+d['report_content']['differences']:f['evidence_ids']=[]
  d['report_content']['headline']='这里只介绍岗位任务，没有个人材料，不作个人诊断。'
  for f in d['report_content']['findings']:
   f['title']='岗位任务说明';f['text']='岗位强调任务定义、方案取舍与结果反馈；没有个人材料，只解释职责。'
  for df in d['report_content']['differences']:
   df['personal_evidence']='没有个人材料，不作经历判断。';df['implication']='按任务责任理解该岗位。'
  for a in d['report_content']['actions']:a.update(action_type='market_research',evidence_ids=[])
  self.assertEqual(validate(d),[])
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'input.json';src.write_text(json.dumps(d));out=Path(td)/'report.md';build_v2(d,src,out)
   self.assertIn('岗位理解',out.read_text());self.assertNotIn('你的定位',out.read_text());self.assertEqual(json.loads(out.with_suffix('.chart.json').read_text())['personal_rated'],0)
 def test_html_escaping_and_main_companion_separation(self):
  d=fixture();d['report_content']['headline']='合成 <script>alert(1)</script> 任务定位'
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'input.json';src.write_text(json.dumps(d));out=Path(td)/'report.md';build_v2(d,src,out)
   html=out.with_suffix('.html').read_text();main=out.read_text();ev=out.with_name('report-evidence.md').read_text()
   self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('完整能力树',main);self.assertIn('二级任务映射',ev);self.assertNotIn('待验证',main)
 @unittest.skipUnless(importlib.util.find_spec('reportlab'), 'optional PDF extra not installed')
 def test_pdf_chart_fits_frame_and_keeps_aspect_after_lazy_loading(self):
  from report_export import chart_flowable
  from reportlab.lib.utils import ImageReader
  chart=next((ROOT/'examples').glob('synthetic-v02-report-*.png'))
  image=chart_flowable(chart);source_width,source_height=ImageReader(str(chart)).getSize()
  _=image.imageWidth
  width,height=image.wrap(511,750)
  self.assertLessEqual(width,511);self.assertAlmostEqual(width/height,source_width/source_height)
if __name__=='__main__':unittest.main()

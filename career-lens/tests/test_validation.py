import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_input import validate
from normalize_jds import normalize

def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))

class DiagnosisValidationTests(unittest.TestCase):
    def test_synthetic_scored_flow_passes(self):
        self.assertEqual(validate(load("synthetic-case.json")), [])

    def test_jd_only_real_market_exploration_passes_without_personal_scores(self):
        data = load("real-exploratory-market.json")
        self.assertEqual(validate(data), [])
        self.assertEqual(data["candidate_evidence"]["assessments"], [])
        self.assertTrue(all(d["market_level"] is None for d in data["market_model"]["dimensions"]))

    def test_skipped_baseline_cannot_claim_belief_gap(self):
        data = load("real-exploratory-market.json")
        data["report_content"]["three_conclusions"][0] = "你存在认知盲区。"
        self.assertTrue(validate(data))

    def test_unknown_never_receives_low_score_but_can_keep_ambiguous_evidence(self):
        data = load("synthetic-case.json")
        rec = next(x for x in data["candidate_evidence"]["assessments"] if x["status"] == "unknown")
        rec["score"] = 1
        self.assertTrue(any("unknown requires null" in e for e in validate(data)))
        rec["score"] = None
        data["candidate_evidence"]["evidence"].append({"evidence_id":"EV-AMBIG", "capability_id":rec["dimension_id"], "source_material_id":"MAT-1", "source_excerpt_or_summary":"合成：含糊表述，尚不能判断本人责任。", "evidence_type":"unknown", "involvement":"unknown", "outcome":None, "strength":"weak"})
        rec["evidence_ids"] = ["EV-AMBIG"]
        self.assertEqual(validate(data), [])

    def test_exploratory_market_cannot_have_numeric_ratings(self):
        data = load("synthetic-case.json")
        data["market_model"]["market_confidence"] = "exploratory_only"
        self.assertTrue(any("cannot carry market levels" in e for e in validate(data)))

    def test_market_source_reference_must_resolve(self):
        data = load("synthetic-case.json")
        data["market_model"]["dimensions"][0]["supporting_sources"] = ["missing"]
        self.assertTrue(any("included, in-scope JD records" in e for e in validate(data)))

    def test_every_scored_market_dimension_needs_five_anchors(self):
        data = load("synthetic-case.json")
        data["market_model"]["dimensions"][0]["rubric"].pop()
        self.assertTrue(any("one behavior anchor" in e for e in validate(data)))

    def test_platform_role_is_not_mixed_into_application_market(self):
        data = load("synthetic-case.json")
        data["sources"][0]["role_track"] = "ai_platform_pm"
        self.assertTrue(any("does not match the target" in e for e in validate(data)))

    def test_expired_jd_cannot_count_as_included(self):
        data = load("synthetic-case.json")
        data["sources"][0]["source_status"] = "expired"
        self.assertTrue(any("expired JD cannot be included" in e for e in validate(data)))

    def test_boolean_and_fractional_ratings_are_rejected(self):
        data = load("synthetic-case.json")
        data["candidate_evidence"]["assessments"][0]["score"] = True
        self.assertTrue(validate(data))
        data = load("synthetic-case.json")
        data["market_model"]["dimensions"][0]["market_level"] = 3.5
        self.assertTrue(validate(data))

    def test_missing_evidence_reference_is_rejected(self):
        data = load("synthetic-case.json")
        data["candidate_evidence"]["assessments"][0]["evidence_ids"] = ["EV-NOT-FOUND"]
        self.assertTrue(any("unknown evidence ID" in e for e in validate(data)))

    def test_verified_behavior_at_or_above_market_level_cannot_be_called_capability_gap(self):
        data = load("synthetic-case.json")
        assessment = next(a for a in data["candidate_evidence"]["assessments"] if a["dimension_id"] == "evaluation")
        dim = next(d for d in data["market_model"]["dimensions"] if d["id"] == assessment["dimension_id"])
        assessment["score"] = dim["market_level"]
        self.assertTrue(any("capability_gap requires" in e for e in validate(data)))

    def test_confirmed_gap_can_be_unrated_when_specific_missing_behavior_is_evidenced(self):
        data = load("synthetic-case.json")
        assessment = next(a for a in data["candidate_evidence"]["assessments"] if a["dimension_id"] == "evaluation")
        assessment["status"] = "confirmed_gap"
        assessment["score"] = None
        assessment["missing_evidence"] = ["缺少可复盘的线上评测行为证据"]
        self.assertEqual(validate(data), [])

    def test_synthetic_fixture_cannot_be_relabelled_as_real(self):
        data = load("synthetic-case.json")
        data["synthetic"] = False
        self.assertTrue(any("fixture markers" in e for e in validate(data)))

    def test_excluded_posting_cannot_support_a_market_rating(self):
        data = load("synthetic-case.json")
        data["sources"][0]["eligibility"] = "excluded_platform"
        data["market_model"]["eligible_jd_count"] = 0
        self.assertTrue(any("included, in-scope JD records" in e for e in validate(data)))

    def test_market_track_must_match_target(self):
        data = load("synthetic-case.json")
        data["market_model"]["role_track"] = "ai_platform_pm"
        self.assertTrue(any("must match the selected target" in e for e in validate(data)))

    def test_belief_comparison_must_link_to_original_baseline(self):
        data = load("synthetic-case.json")
        data["beliefs"][0]["statement"] = "A made-up prior belief"
        self.assertTrue(any("preserve the original user statement" in e for e in validate(data)))

    def test_intake_references_must_resolve(self):
        data = load("synthetic-case.json")
        data["intake"]["provided_jd_ids"] = ["MISSING-JD"]
        data["intake"]["candidate_material_ids"] = ["MISSING-MATERIAL"]
        errors = validate(data)
        self.assertTrue(any("provided_jd_ids" in e for e in errors))
        self.assertTrue(any("candidate_material_ids" in e for e in errors))

    def test_gap_action_cannot_be_unlinked_from_capability_or_evidence(self):
        data = load("synthetic-case.json")
        action = next(a for a in data["report_content"]["actions"] if a["action_type"] == "capability_gap")
        action["capability_ids"] = []
        action["evidence_ids"] = []
        errors = validate(data)
        self.assertTrue(any("gap actions must link" in e for e in errors))
        self.assertTrue(any("must link supporting evidence" in e for e in errors))

    def test_unknown_jd_status_stays_pending(self):
        raw = [{"organization":"Acme", "title":"AI应用PM", "role_track":"ai_application_pm", "location":"北京", "seniority":"3–5年", "collected_at":"2026-10-10", "url":"https://example.com/1", "description_summary":"未知状态", "source_status":"unknown"}]
        self.assertEqual(normalize(raw)[0]["eligibility"], "pending_review")

    def test_normalizer_flags_duplicate_platform_and_expired_records(self):
        raw = [
            {"organization":"Acme", "title":"AI应用产品经理", "role_track":"ai_application_pm", "location":"北京", "seniority":"3–5年", "collected_at":"2026-10-10", "url":"https://example.com/1", "description_summary":"业务应用任务", "source_status":"active"},
            {"organization":"Acme", "title":"AI应用产品经理", "role_track":"ai_application_pm", "location":"北京", "seniority":"3–5年", "collected_at":"2026-10-10", "url":"https://example.com/2", "description_summary":"业务应用任务", "source_status":"active"},
            {"organization":"Other", "title":"AI平台产品经理", "role_track":"ai_platform_pm", "location":"北京", "seniority":"3–5年", "collected_at":"2026-10-10", "url":"https://example.com/3", "description_summary":"模型平台", "source_status":"active"},
            {"organization":"Old", "title":"AI应用PM", "role_track":"ai_application_pm", "location":"北京", "seniority":"3–5年", "collected_at":"2026-10-10", "url":"https://example.com/4", "description_summary":"已过期", "source_status":"expired"}
        ]
        rows = normalize(raw)
        self.assertEqual([r["eligibility"] for r in rows], ["included", "duplicate_candidate", "excluded_platform", "excluded_expired"])
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "input.json", Path(tmp) / "normalized.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "normalize_jds.py"), str(source), str(output)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(validate(json.loads(output.read_text()), "jd.schema.json"), [])

    def test_real_exploration_report_uses_table_without_radar(self):
        data = load("real-exploratory-market.json")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report.py"), str(ROOT / "examples" / "real-exploratory-market.json"), str(out)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = out.read_text(encoding="utf-8")
            self.assertIn("不能判断用户存在认知盲区", report)
            self.assertIn("未提供个人简历", report)
            self.assertNotIn("![](", report)
            self.assertIn("https://www.zhaopin.com/jobdetail/CC409922380J41025925902.htm", report)

if __name__ == "__main__": unittest.main()

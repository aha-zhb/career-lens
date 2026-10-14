#!/usr/bin/env python3
"""Validate a Career Lens input with JSON Schema and semantic cross-reference checks."""
import argparse, json, sys
from urllib.parse import urlsplit
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"

def bounds(obj, point, interval):
    value = obj.get(point)
    return [value, value] if value is not None else obj.get(interval)

def check_interval(obj, point, interval, path, errors):
    band = obj.get(interval)
    if band:
        if obj.get(point) is not None:
            errors.append(f"{path}: use a point OR a level range, not both")
        if band[0] > band[1]:
            errors.append(f"{path}.{interval}: range must be ordered")

def check_v2_market(market, errors):
    rated = []
    for i, dim in enumerate(market.get("dimensions", [])):
        path = f"market_model.dimensions[{i}]"
        check_interval(dim, "market_level", "market_level_range", path, errors)
        level = bounds(dim, "market_level", "market_level_range")
        rated.append(bool(level))
        review = dim.get("rating_review", {})
        if level and (review.get("approved") is not True or not review.get("rationale", "").strip()):
            errors.append(f"{path}: rated dimension requires its own approved rating_review")
        if not level and review.get("approved"):
            errors.append(f"{path}: approved rating requires a point or range")
    confidence = market.get("market_confidence")
    expected = "sufficient_for_rating" if rated and all(rated) else "mixed" if any(rated) else None
    if expected and confidence != expected:
        errors.append("market_model.market_confidence: must describe per-dimension coverage")
    if not expected and confidence not in ("insufficient", "exploratory_only"):
        errors.append("market_model.market_confidence: unrated model must remain exploratory or insufficient")
    if market.get("quality_review", {}).get("approved_for_rating") != any(rated):
        errors.append("market_model.quality_review: approval must reflect the reviewed rated dimensions")
    tree = market.get("capability_tree", [])
    ids = [x["id"] for x in tree]
    if len(ids) != len(set(ids)):
        errors.append("market_model.capability_tree: duplicate IDs")
    dim_ids = {d["id"] for d in market.get("dimensions", [])}
    for item in tree:
        if item["parent_dimension_id"] not in dim_ids:
            errors.append("market_model.capability_tree: unknown parent dimension")
    for dim in market.get("dimensions", []):
        if set(dim.get("component_ids", [])) != {x["id"] for x in tree if x["parent_dimension_id"] == dim["id"]}:
            errors.append("market_model.capability_tree: dimension components must match the full task tree")

def check_v2_assessment(assessment, path, errors):
    check_interval(assessment, "score", "score_range", path, errors)
    band = assessment.get("score_range")
    if band and (assessment.get("status") == "unknown" or not assessment.get("evidence_ids") or not assessment.get("rationale", "").strip()):
        errors.append(f"{path}: level range requires assessed behavioral evidence; unknown requires null")

def check_v2_report(data, errors):
    content = data["report_content"]
    dims = {d["id"] for d in data["market_model"]["dimensions"]}
    sources = {s["id"]: s for s in data["sources"]}
    evidence = {e["evidence_id"]: e for e in data["candidate_evidence"]["evidence"]}
    if sorted(f["kind"] for f in content["findings"]) != ["advantage", "obstacle", "reframe"]:
        errors.append("report_content.findings: include one advantage, obstacle and reframe")
    for section in ("findings", "differences"):
        for i, item in enumerate(content[section]):
            path = f"report_content.{section}[{i}]"
            if not item["capability_ids"] or set(item["capability_ids"]) - dims:
                errors.append(f"{path}: conclusions must link valid capabilities")
            if not item["source_ids"] or set(item["source_ids"]) - set(sources):
                errors.append(f"{path}: conclusions must link traceable market sources")
            elif any(sources[s]["eligibility"] != "included" for s in item["source_ids"]):
                errors.append(f"{path}: conclusions cannot cite excluded/pending sources")
            if set(item["evidence_ids"]) - set(evidence):
                errors.append(f"{path}: unknown evidence ID")
            for eid in item["evidence_ids"]:
                if eid in evidence and evidence[eid]["capability_id"] not in item["capability_ids"]:
                    errors.append(f"{path}: evidence must support a linked capability")
            if data["candidate_evidence"]["materials"] and not item["evidence_ids"]:
                errors.append(f"{path}: personal conclusions require supplied evidence")
    public = json.dumps({k: content[k] for k in ("headline", "findings", "differences", "scope_summary")}, ensure_ascii=False)
    if any(p in public for p in ("等级未决", "待验证", "null", "verified", "unresolved")):
        errors.append("report_content: replace internal pending labels with concrete positioning and scoped implications")
    if not content["actions"]:
        errors.append("report_content.actions: V0.2 requires an actionable next step")
    if data["candidate_evidence"]["materials"] and any(a["action_type"] == "market_research" for a in content["actions"]):
        errors.append("report_content.actions: market research belongs to the agent, not the candidate action plan")

def validate(data, schema_name="diagnosis.schema.json"):
    registry = Registry()
    for path in SCHEMAS.glob("*.schema.json"):
        content = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(content["$id"], Resource.from_contents(content))
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker(), registry=registry)
    if schema_name == "jd.schema.json" and isinstance(data, list):
        jd_schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
        jd_validator = Draft202012Validator(jd_schema, format_checker=FormatChecker())
        errors = []
        for i, row in enumerate(data):
            errors.extend(f"[{i}].{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}" for e in jd_validator.iter_errors(row))
        if errors:
            return errors
        ids = [row.get("id") for row in data if isinstance(row, dict)]
        if len(ids) != len(set(ids)): errors.append("$: duplicate JD ids")
        for i, row in enumerate(data):
            if row.get("url") and urlsplit(row["url"]).scheme not in ("http", "https"):
                errors.append(f"[{i}]: source URL must use http or https")
            if row.get("source_layer"):
                if row.get("eligibility") == "included" and row.get("body_access") != "full":
                    errors.append(f"[{i}]: included source needs reviewed body")
                if (row.get("source_kind") == "practice") != (row["source_layer"] == "work_practice"):
                    errors.append(f"[{i}]: practice sources must be separated from job sources")
            if row.get("source_status") in ("unknown", "unavailable") and row.get("eligibility") == "included":
                errors.append(f"[{i}]: unverified or unavailable source must stay pending_review")
            if row.get("source_status") == "expired" and row.get("eligibility") == "included":
                errors.append(f"[{i}]: expired source cannot be included")
        return errors
    errors = [f"{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}" for e in validator.iter_errors(data)]
    if errors:
        return errors
    if not isinstance(data, dict): return errors
    v2 = data.get("schema_version") == "0.2"
    if not v2 and any(key in json.dumps(data) for key in ('"market_level_range"', '"score_range"', '"rating_review"')):
        errors.append("schema_version: range ratings and per-dimension reviews require V0.2")
    if schema_name == "candidate-evidence.schema.json":
        material_ids = [m["id"] for m in data["materials"]]
        evidence_ids = [e["evidence_id"] for e in data["evidence"]]
        assessment_ids = [a["dimension_id"] for a in data["assessments"]]
        for name, ids in (("materials", material_ids), ("evidence", evidence_ids), ("assessments", assessment_ids)):
            if len(ids) != len(set(ids)): errors.append(f"{name}: duplicate IDs")
        evidence_map = {e["evidence_id"]: e for e in data["evidence"]}
        for i, evidence in enumerate(data["evidence"]):
            if evidence["source_material_id"] not in material_ids:
                errors.append(f"evidence[{i}].source_material_id: unknown material ID")
        for i, assessment in enumerate(data.get("assessments", [])):
            status, score = assessment.get("status"), assessment.get("score")
            refs = assessment.get("evidence_ids", [])
            if set(refs) - set(evidence_ids): errors.append(f"assessments[{i}].evidence_ids: unknown evidence ID")
            if any(evidence_map[eid]["capability_id"] != assessment["dimension_id"] for eid in refs if eid in evidence_map):
                errors.append(f"assessments[{i}].evidence_ids: evidence is linked to another capability")
            if status in ("verified", "partial", "confirmed_gap") and (not refs or not assessment["rationale"].strip()):
                errors.append(f"assessments[{i}]: assessed state requires evidence refs and rationale")
            if status == "confirmed_gap" and not assessment["missing_evidence"]:
                errors.append(f"assessments[{i}]: confirmed gap needs a specific missing behavior")
            if status == "unknown" and score is not None: errors.append(f"assessments[{i}].score: unknown requires null")
            if status == "verified" and not (v2 and assessment.get("score_range")) and (not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5 or not refs):
                errors.append(f"assessments[{i}]: verified requires integer score 1–5 and evidence refs")
            if status in ("partial", "confirmed_gap") and score is not None and (not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5):
                errors.append(f"assessments[{i}].score: use integer 1–5 or null")
            if v2: check_v2_assessment(assessment, f"assessments[{i}]", errors)
        for event in data.get("events", []):
            if set(event["material_ids"]) - set(material_ids): errors.append("events: unknown material ID")
        return errors
    if schema_name == "market-profile.schema.json":
        for i, dim in enumerate(data.get("dimensions", [])):
            levels = [a.get("level") for a in dim.get("rubric", [])]
            if sorted(levels) != [1, 2, 3, 4, 5]: errors.append(f"dimensions[{i}].rubric: provide one anchor for each level 1–5")
            level = dim.get("market_level")
            if level is not None and (not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 5):
                errors.append(f"dimensions[{i}].market_level: use integer 1–5 or null")
            if not v2 and data.get("market_confidence") != "sufficient_for_rating" and level is not None:
                errors.append(f"dimensions[{i}].market_level: exploratory profile must keep level null")
        if v2: check_v2_market(data, errors)
        return errors
    if schema_name == "intake.schema.json":
        if data.get("prior_belief_status") == "skipped" and data.get("prior_beliefs"):
            errors.append("prior_beliefs: must be empty when baseline is skipped")
        if data.get("prior_belief_status") == "captured" and not data.get("prior_beliefs"):
            errors.append("prior_beliefs: captured baseline requires an original belief")
        return errors
    if schema_name != "diagnosis.schema.json": return errors

    sources = data.get("sources", [])
    source_ids = [s.get("id") for s in sources if isinstance(s, dict)]
    market = data.get("market_model", {})
    intake = data.get("intake", {})
    dims = market.get("dimensions", [])
    dim_ids = [d.get("id") for d in dims if isinstance(d, dict)]
    if len(source_ids) != len(set(source_ids)): errors.append("sources: duplicate source ids")
    if set(intake.get("provided_jd_ids", [])) - set(source_ids): errors.append("intake.provided_jd_ids: contains a JD ID absent from the source registry")
    if len(dim_ids) != len(set(dim_ids)): errors.append("market_model.dimensions: duplicate capability ids")
    job_sources = [s for s in sources if s.get("source_kind", "job") == "job"]
    if market.get("eligible_jd_count") != sum(1 for s in job_sources if s.get("eligibility") == "included"):
        errors.append("market_model.eligible_jd_count: must equal the number of included source records")
    if market.get("candidate_jd_count") != len(job_sources): errors.append("market_model.candidate_jd_count: must equal the source registry candidate count")
    target_track = intake.get("target", {}).get("role_track")
    allowed_tracks = {"ai_application_pm", "ai_agent_application_pm"} if target_track == "ai_application_pm" else {target_track}
    if market.get("role_track") not in allowed_tracks:
        errors.append("market_model.role_track: must match the selected target track")
    for i, source in enumerate(sources):
        practice = source.get("source_kind") == "practice"
        shared_application = v2 and source.get("source_layer") == "role_benchmark" and source.get("role_track") in ("ai_application_pm", "ai_agent_application_pm")
        if source.get("url") and urlsplit(source["url"]).scheme not in ("http", "https"):
            errors.append(f"sources[{i}]: source URL must use http or https")
        if source.get("eligibility") == "included" and not practice and not shared_application and source.get("role_track") not in allowed_tracks:
            errors.append(f"sources[{i}]: included job track does not match the target; separate platform/other tracks")
        if source.get("source_status") == "expired" and source.get("eligibility") == "included":
            errors.append(f"sources[{i}]: expired JD cannot be included")
        if source.get("eligibility") == "included" and source.get("source_status") in ("unknown", "unavailable"):
            errors.append(f"sources[{i}]: unknown or unavailable source status must stay pending_review")
        if v2:
            if source.get("source_layer") not in ("target_market", "role_benchmark", "work_practice"):
                errors.append(f"sources[{i}]: V0.2 source needs an explicit source_layer")
            if practice != (source.get("source_layer") == "work_practice"):
                errors.append(f"sources[{i}]: practice sources must be separated from job sources")
            if source.get("eligibility") == "included" and source.get("body_access") != "full":
                errors.append(f"sources[{i}]: included source needs reviewed body, not a search summary")
            if market.get("geography_mode", "location_first") == "location_first" and source.get("source_layer") == "target_market" and source.get("eligibility") == "included" and source.get("location") != intake["target"]["location"]:
                errors.append(f"sources[{i}]: target-market source geography must match the target")
        if market.get("market_confidence") == "sufficient_for_rating" and not data.get("synthetic") and source.get("eligibility") == "included" and source.get("source_status") != "active":
            errors.append(f"sources[{i}]: a real scored market model requires active status verified at collection")
    if set(market.get("sources", [])) - set(source_ids): errors.append("market_model.sources: contains an unknown source id")
    included_ids = {s.get("id") for s in sources if s.get("eligibility") == "included"}
    if set(market.get("sources", [])) - included_ids: errors.append("market_model.sources: only reviewed, in-scope included JD records may support a market profile")
    for i, dim in enumerate(dims):
        refs = dim.get("supporting_sources", [])
        if not refs: errors.append(f"market_model.dimensions[{i}].supporting_sources: at least one traceable source is required")
        if set(refs) - included_ids: errors.append(f"market_model.dimensions[{i}].supporting_sources: must cite included, in-scope JD records")
        anchors = [a.get("level") for a in dim.get("rubric", [])]
        if sorted(anchors) != [1, 2, 3, 4, 5]: errors.append(f"market_model.dimensions[{i}].rubric: provide one behavior anchor for each level 1–5")
        level = dim.get("market_level")
        if level is not None and (not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 5):
            errors.append(f"market_model.dimensions[{i}].market_level: must be integer 1–5 or null")
        if v2 and bounds(dim, "market_level", "market_level_range") and not data.get("synthetic"):
            review = dim.get("rating_review", {})
            rating_sources = [s for s in sources if s["id"] in refs and s.get("source_kind", "job") == "job" and s["source_status"] == "active"]
            if review.get("scope") == "target_market":
                rating_sources = [s for s in rating_sources if s.get("source_layer") == "target_market"]
            if not rating_sources:
                errors.append(f"market_model.dimensions[{i}]: rating requires active job responsibility evidence in its stated scope; practice alone is insufficient")
    radar_ids = market.get("radar_dimension_ids")
    if radar_ids is not None:
        if len(radar_ids) < 3 or len(radar_ids) > 8: errors.append("market_model.radar_dimension_ids: select 3–8 readable dimensions")
        if set(radar_ids) - set(dim_ids): errors.append("market_model.radar_dimension_ids: contains an unknown capability ID")
    if v2 and data["report_content"].get("chart_mode") == "radar" and not any(bounds(d, "market_level", "market_level_range") for d in dims if radar_ids is None or d["id"] in radar_ids):
        errors.append("report_content.chart_mode: radar requires supported market ratings on selected axes")
    confidence = market.get("market_confidence")
    approved = market.get("quality_review", {}).get("approved_for_rating")
    if not v2 and (confidence == "sufficient_for_rating") != (approved is True): errors.append("market_model.quality_review.approved_for_rating: must agree with market_confidence and be explicitly reviewed")
    if not v2 and confidence != "sufficient_for_rating" and any(d.get("market_level") is not None for d in dims):
        errors.append("market_model.dimensions: exploratory or insufficient evidence cannot carry market levels")
    if v2:
        if market.get("schema_version") != "0.2" or data["candidate_evidence"].get("schema_version") != "0.2":
            errors.append("schema_version: composed V0.2 requires versioned market and candidate layers")
        check_v2_market(market, errors)
        for tree_item in market.get("capability_tree", []):
            if set(tree_item["source_ids"]) - included_ids: errors.append("market_model.capability_tree: unknown or excluded source")
        for rnd in market.get("research_rounds", []):
            if set(rnd["new_source_ids"]) - set(source_ids): errors.append("market_model.research_rounds: unknown source ID")

    if intake.get("prior_belief_status") == "skipped" and data.get("beliefs"):
        errors.append("beliefs: must be empty when the prior belief baseline was skipped")
    if intake.get("prior_belief_status") == "captured" and not intake.get("prior_beliefs"):
        errors.append("intake.prior_beliefs: captured baseline requires at least one original belief")
    original_beliefs = {b.get("belief_id"): b.get("statement") for b in intake.get("prior_beliefs", [])}
    comparison_ids = [b.get("belief_id") for b in data.get("beliefs", [])]
    if len(comparison_ids) != len(set(comparison_ids)): errors.append("beliefs: duplicate original-belief reference")
    for i, belief in enumerate(data.get("beliefs", [])):
        if belief.get("belief_id") not in original_beliefs: errors.append(f"beliefs[{i}].belief_id: must reference an original captured belief")
        elif belief.get("statement") != original_beliefs[belief.get("belief_id")]: errors.append(f"beliefs[{i}].statement: must preserve the original user statement")
        if set(belief.get("dimension_refs", [])) - set(dim_ids): errors.append(f"beliefs[{i}].dimension_refs: contains an unknown capability id")
    if intake.get("prior_belief_status") == "skipped":
        narrative = json.dumps(data.get("report_content", {}), ensure_ascii=False)
        phrases = ("你以前不知道", "你之前不知道", "你原来不知道", "你未意识到", "你没有意识到", "你的认知盲区", "你存在认知盲区", "你低估了")
        if any(phrase in narrative for phrase in phrases): errors.append("report_content.three_conclusions: no personal blind-spot claim without a captured baseline")

    candidate = data.get("candidate_evidence", {})
    materials = candidate.get("materials", [])
    material_ids = [m.get("id") for m in materials if isinstance(m, dict)]
    if len(material_ids) != len(set(material_ids)): errors.append("candidate_evidence.materials: duplicate IDs")
    if set(intake.get("candidate_material_ids", [])) - set(material_ids): errors.append("intake.candidate_material_ids: contains a material ID absent from candidate_evidence.materials")
    evidence = candidate.get("evidence", [])
    evidence_map = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    evidence_ids = [e.get("evidence_id") for e in evidence if isinstance(e, dict)]
    if len(evidence_ids) != len(set(evidence_ids)): errors.append("candidate_evidence.evidence: duplicate IDs")
    for i, ev in enumerate(evidence):
        if ev.get("capability_id") not in dim_ids: errors.append(f"candidate_evidence.evidence[{i}].capability_id: unknown capability")
        if ev.get("source_material_id") not in material_ids: errors.append(f"candidate_evidence.evidence[{i}].source_material_id: unknown material")
    assessments = candidate.get("assessments", [])
    assessment_ids = [a.get("dimension_id") for a in assessments if isinstance(a, dict)]
    if len(assessment_ids) != len(set(assessment_ids)): errors.append("candidate_evidence.assessments: duplicate capability assessment")
    if materials and set(assessment_ids) != set(dim_ids): errors.append("candidate_evidence.assessments: map every market dimension exactly once when candidate materials are present")
    if not materials and (evidence or assessments): errors.append("candidate_evidence: cannot assess personal evidence without user-provided material")
    for i, assessment in enumerate(assessments):
        status, score, refs = assessment.get("status"), assessment.get("score"), assessment.get("evidence_ids", [])
        if set(refs) - set(evidence_map): errors.append(f"candidate_evidence.assessments[{i}].evidence_ids: unknown evidence ID")
        for eid in refs:
            if eid in evidence_map and evidence_map[eid].get("capability_id") != assessment.get("dimension_id"):
                errors.append(f"candidate_evidence.assessments[{i}].evidence_ids: evidence is linked to another capability")
        if status == "unknown" and score is not None:
            errors.append(f"candidate_evidence.assessments[{i}].score: unknown requires null; ambiguous/conflicting evidence refs may be retained")
        if status in ("verified", "partial", "confirmed_gap") and (not refs or not assessment.get("rationale", "").strip()):
            errors.append(f"candidate_evidence.assessments[{i}]: assessed state requires evidence refs and rationale")
        if status == "verified" and not (v2 and assessment.get("score_range")) and (not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5):
            errors.append(f"candidate_evidence.assessments[{i}].score: verified requires an integer 1–5")
        if status in ("partial", "confirmed_gap") and score is not None and (not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5):
            errors.append(f"candidate_evidence.assessments[{i}].score: use integer 1–5 or null")
        if status == "confirmed_gap" and (not refs or not assessment.get("missing_evidence")):
            errors.append(f"candidate_evidence.assessments[{i}]: confirmed gap needs supporting assessment evidence and a specific missing behavior")
        if v2: check_v2_assessment(assessment, f"candidate_evidence.assessments[{i}]", errors)
    for event in candidate.get("events", []):
        if set(event["material_ids"]) - set(material_ids): errors.append("candidate_evidence.events: unknown material ID")
    assessment_map = {a.get("dimension_id"): a for a in assessments if isinstance(a, dict)}
    evidence_by_material_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    for i, action in enumerate(data.get("report_content", {}).get("actions", [])):
        if set(action.get("capability_ids", [])) - set(dim_ids): errors.append(f"report_content.actions[{i}].capability_ids: unknown capability ID")
        if set(action.get("evidence_ids", [])) - set(evidence_by_material_id): errors.append(f"report_content.actions[{i}].evidence_ids: unknown evidence ID")
        if action.get("action_type") in ("capability_gap", "evidence_gap") and not action.get("capability_ids"):
            errors.append(f"report_content.actions[{i}]: gap actions must link at least one capability")
        if action.get("action_type") == "capability_gap" and not action.get("evidence_ids"):
            errors.append(f"report_content.actions[{i}]: capability_gap must link supporting evidence")
        for eid in action.get("evidence_ids", []):
            ev = evidence_by_material_id.get(eid)
            if ev and action.get("capability_ids") and ev.get("capability_id") not in action.get("capability_ids", []):
                errors.append(f"report_content.actions[{i}].evidence_ids: evidence must support one of the linked capabilities")
        for cap in action.get("capability_ids", []):
            assessment = assessment_map.get(cap)
            dim = next((d for d in dims if d.get("id") == cap), {})
            confirmed = assessment and assessment.get("status") == "confirmed_gap"
            pb = bounds(assessment or {}, "score", "score_range")
            mb = bounds(dim, "market_level", "market_level_range")
            supported_below_market = assessment and assessment.get("status") == "verified" and pb and mb and pb[1] < mb[0]
            if action.get("action_type") == "capability_gap" and not (confirmed or supported_below_market):
                errors.append(f"report_content.actions[{i}]: capability_gap requires a confirmed gap or verified behavior below a rated market level")
            if action.get("action_type") == "evidence_gap" and (not assessment or assessment.get("status") not in ("partial", "unknown")):
                errors.append(f"report_content.actions[{i}]: evidence_gap must remain distinct from a confirmed capability gap")
    material_ids_set = set(material_ids)
    if v2: check_v2_report(data, errors)
    for i, revision in enumerate(data.get("revision_history", [])):
        if set(revision.get("new_material_ids", [])) - material_ids_set:
            errors.append(f"revision_history[{i}].new_material_ids: unknown material ID")
    if data.get("synthetic"):
        limitations = " ".join(market.get("sample_limitations", []))
        if "合成" not in limitations and "synthetic" not in limitations.lower(): errors.append("synthetic case must disclose synthetic market data")
        for i, source in enumerate(sources):
            if source.get("source_status") != "user_provided" and source.get("eligibility") != "pending_review":
                errors.append(f"sources[{i}]: synthetic demonstration sources must be visibly fictional/pending review")
        for i, ev in enumerate(evidence):
            text = ev.get("source_excerpt_or_summary", "")
            if "合成" not in text and "虚构" not in text: errors.append(f"candidate_evidence.evidence[{i}]: synthetic evidence must be visibly fictional")
    else:
        marker_text = json.dumps({"case_id": data.get("case_id"), "sources": [{"id": s.get("id"), "url": s.get("url")} for s in sources], "sampling_method": market.get("sampling_method"), "sample_limitations": market.get("sample_limitations")}, ensure_ascii=False).lower()
        explicit_markers = ("example.invalid", "synthetic_example", "synthetic demo", "完全合成", "合成演示数据", "仅用于验证格式", "合成示例")
        suspicious = any("example.invalid" in s.get("url", "") or s.get("id", "").upper().startswith("SYNTH") for s in sources)
        if suspicious or any(marker in marker_text for marker in explicit_markers):
            errors.append("synthetic fixture markers found in a case labeled real; do not relabel demonstration data as real evidence")
    return errors

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("--schema", default="diagnosis.schema.json", choices=sorted(p.name for p in SCHEMAS.glob("*.schema.json")))
    args = ap.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        errors = validate(data, args.schema)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr); return 2
    if errors:
        print("INVALID")
        for error in errors: print(f"- {error}")
        return 1
    print("VALID"); return 0

if __name__ == "__main__": raise SystemExit(main())

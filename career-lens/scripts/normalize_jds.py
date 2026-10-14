#!/usr/bin/env python3
"""Normalize manually collected JD records and flag duplicates / out-of-scope tracks."""
import argparse, hashlib, json, re, sys
from pathlib import Path
from validate_input import validate

APPLICATION = {"ai_application_pm", "ai_agent_application_pm"}
def normalize(records, target_tracks=APPLICATION):
    seen = set(); result = []
    for i, raw in enumerate(records):
        title = str(raw.get("title", "")).strip()
        organization = str(raw.get("organization", "")).strip()
        location = str(raw.get("location", "")).strip()
        summary = str(raw.get("description_summary", "")).strip()
        canonical = "|".join(re.sub(r"\s+", " ", x).casefold() for x in (organization, title, location, summary))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        status = raw.get("source_status", "unknown")
        track = raw.get("role_track", "uncertain")
        practice = raw.get("source_kind") == "practice"
        if status == "expired":
            eligibility, why = "excluded_expired", "来源记录标记为已过期"
        elif status in ("unknown", "unavailable"):
            eligibility, why = "pending_review", "来源活跃状态或适用范围尚待核实"
        elif raw.get("source_layer") and raw.get("body_access") != "full":
            eligibility, why = "pending_review", "分层来源尚无可审阅完整正文；搜索摘要只作线索"
        elif fingerprint in seen:
            eligibility, why = "duplicate_candidate", "与前序岗位的公司、标题、地区和职责摘要指纹重复，待人工复核"
        elif not practice and track == "ai_platform_pm":
            eligibility, why = "excluded_platform", "AI平台产品岗位，排除出首发B端AI应用产品画像"
        elif not practice and track not in target_tracks and not (raw.get("source_layer") == "role_benchmark" and track in APPLICATION):
            eligibility, why = "excluded_other_track", f"岗位方向 {track} 与目标方向不符或尚未归类"
        elif status == "user_provided":
            eligibility, why = "included", "用户提供正文且方向经人工审查；活跃状态未核验，只可用于探索画像"
        else:
            eligibility, why = "included", None
        seen.add(fingerprint)
        row = {
            "id": str(raw.get("id") or f"JD-{i+1:03d}"), "organization": organization, "title": title,
            "role_track": track, "location": location, "seniority": str(raw.get("seniority", "未注明")),
            "collected_at": raw["collected_at"], "published_at": raw.get("published_at"), "url": raw.get("url"),
            "description_summary": summary, "responsibilities": raw.get("responsibilities", []), "requirements": raw.get("requirements", []),
            "source_status": status, "source_status_note": raw.get("source_status_note") or ("活跃状态未核实；如用于真实市场评分，须重新检查招聘页。" if status == "user_provided" else None),
            "eligibility": eligibility, "exclusion_reason": why, "dedupe_fingerprint": fingerprint
        }
        for key in ("source_kind", "source_layer", "body_access"):
            if key in raw: row[key] = raw[key]
        result.append(row)
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="JSON array of manually collected job records")
    ap.add_argument("output", type=Path)
    ap.add_argument("--target-track", choices=["ai_application_pm", "ai_agent_application_pm"], default="ai_application_pm")
    args = ap.parse_args()
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, list): raise ValueError("input root must be a JSON array")
        tracks = APPLICATION if args.target_track == "ai_application_pm" else {args.target_track}
        rows = normalize(raw, tracks)
        errors = validate(rows, "jd.schema.json")
        if errors:
            for error in errors: print(f"INVALID: {error}", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2
    print(f"NORMALIZED: {len(rows)} records ({sum(r['eligibility']=='included' for r in rows)} included)")
    return 0
if __name__ == "__main__": raise SystemExit(main())

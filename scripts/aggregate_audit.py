#!/usr/bin/env python3
"""Aggregate batch audit results and produce final deliverables."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = ROOT / "data" / "audit-batches"
DATA_DIR = ROOT / "data"

# Schema for full audit
AUDIT_SCHEMA = {
    "checked_at": "ISO timestamp",
    "auditor": "Hermes automated documentation audit",
    "method": "Parallel subagent browser verification across 10 batches of 10 apps each",
    "summary": {
        "apps_checked": 0,
        "fields_checked": 0,
        "confirmed": 0,
        "corrected": 0,
        "insufficient_evidence": 0,
        "conflicting_documentation": 0,
        "source_unavailable": 0
    },
    "apps": []
}

def aggregate_batches():
    """Collect all batch results and build the full audit."""
    now = datetime.now(timezone.utc).isoformat()
    
    audit = {**AUDIT_SCHEMA, "checked_at": now}
    summary = {
        "apps_checked": 0,
        "fields_checked": 0,
        "confirmed": 0,
        "corrected": 0,
        "insufficient_evidence": 0,
        "conflicting_documentation": 0,
        "source_unavailable": 0
    }
    
    corrections = []  # List of corrected fields
    unresolved = []   # List of unresolved facts
    
    # Collect batch results
    batch_results = []
    for i in range(1, 11):
        result_file = BATCH_DIR / f"batch-{i:02d}.json"
        if result_file.exists():
            with open(result_file) as f:
                batch = json.load(f)
                batch_results.append(batch)
    
    print(f"Found {len(batch_results)} completed batches")
    
    # Process each batch
    for batch in batch_results:
        apps = batch.get("apps", [])
        for app_data in apps:
            app_id = app_data.get("id")
            app_name = app_data.get("app")
            
            checks = app_data.get("checks", [])
            summary["apps_checked"] += 1
            summary["fields_checked"] += len(checks)
            
            app_check = {
                "id": app_id,
                "app": app_name,
                "checks": []
            }
            
            for check in checks:
                outcome = check.get("outcome", "unknown")
                summary[outcome.replace(" ", "_").lower()] += 1
                
                field_check = {
                    "field": check.get("field"),
                    "original_value": check.get("original_value"),
                    "reviewed_value": check.get("reviewed_value"),
                    "outcome": outcome,
                    "reason": check.get("reason", ""),
                    "source_url": check.get("source_url"),
                    "source_title": check.get("source_title"),
                    "checked_at": check.get("checked_at", now)
                }
                
                app_check["checks"].append(field_check)
                
                # Track corrections
                if outcome == "corrected":
                    corrections.append({
                        "id": app_id,
                        "app": app_name,
                        "field": check.get("field"),
                        "old_value": check.get("original_value"),
                        "new_value": check.get("reviewed_value"),
                        "reason": check.get("reason", ""),
                        "source_url": check.get("source_url"),
                        "source_title": check.get("source_title"),
                        "quote": check.get("quote", "")
                    })
                
                # Track unresolved
                if outcome in ("insufficient evidence", "source unavailable"):
                    unresolved.append({
                        "id": app_id,
                        "app": app_name,
                        "field": check.get("field"),
                        "current_value": check.get("original_value"),
                        "issue": check.get("reason", ""),
                        "source_url": check.get("source_url"),
                        "human_check": "Review official documentation for credential eligibility"
                    })
            
            audit["apps"].append(app_check)
    
    # Sort apps by ID
    audit["apps"].sort(key=lambda x: x["id"])
    
    return audit, corrections, unresolved, summary


def main():
    """Run aggregation and write output files."""
    audit, corrections, unresolved, summary = aggregate_batches()
    
    # The published files contain only structured source metadata and review
    # outcomes. They deliberately omit raw crawler text and private reasoning.
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "full-fact-audit.json").write_text(json.dumps(audit, indent=2))
    
    # Write corrections
    (DATA_DIR / "fact-corrections.json").write_text(json.dumps(corrections, indent=2))
    
    # Write unresolved
    (DATA_DIR / "unresolved-facts.json").write_text(json.dumps(unresolved, indent=2))

    status = {
        "checked_at": audit["checked_at"],
        "scope": "AI-assisted documentation review; applicant manual checks remain pending.",
        "apps_checked": summary["apps_checked"],
        "fields_checked": summary["fields_checked"],
        "outcomes": {
            "confirmed_unchanged": summary["confirmed"],
            "corrected_with_cited_evidence": summary["corrected"],
            "insufficient_evidence": summary["insufficient_evidence"],
            "source_unavailable": summary["source_unavailable"],
        },
        "direct_source_urls_captured": sum(
            bool(check["source_url"])
            for app in audit["apps"] for check in app["checks"]
        ),
        "open_fields": summary["insufficient_evidence"] + summary["source_unavailable"],
    }
    (DATA_DIR / "audit-summary.json").write_text(json.dumps(status, indent=2))
    
    # Print summary
    print("\n=== AGGREGATION COMPLETE ===\n")
    print(f"Apps checked: {summary['apps_checked']}")
    print(f"Fields checked: {summary['fields_checked']}")
    print(f"Confirmed: {summary['confirmed']}")
    print(f"Corrected: {summary['corrected']}")
    print(f"Insufficient evidence: {summary['insufficient_evidence']}")
    print(f"Conflicting documentation: {summary['conflicting_documentation']}")
    print(f"Source unavailable: {summary['source_unavailable']}")
    print(f"\nCorrections tracked: {len(corrections)}")
    print(f"Unresolved items: {len(unresolved)}")


if __name__ == "__main__":
    main()

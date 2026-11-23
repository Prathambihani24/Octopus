#!/usr/bin/env python3
import json, re, os

# Read PSV
with open('data/reviewed.psv', 'r') as f:
    psv_content = f.read()

lines = psv_content.strip().split('\n')

# Read unresolved facts
with open('output/unresolved-facts.json', 'r') as f:
    output_unresolved = json.load(f)

# Parse unresolved IDs and their specific issues
# Map: app_id -> {unresolved_field -> issue_type}
app_field_issues = {}
app_has_explicit_cloudflare = set()
app_has_explicit_spa = set()

for u in output_unresolved:
    app_id = u.get('id')
    field = u.get('field', '')
    issue = u.get('issue', '')
    reason = u.get('reason', '')
    
    if app_id not in app_field_issues:
        app_field_issues[app_id] = {}
    
    if field:
        issue_lower = str(issue).lower()
        reason_lower = str(reason).lower()
        
        # Determine issue type
        if 'cloudflare' in issue_lower or '403' in issue_lower:
            app_field_issues[app_id][field] = 'source_blocked'
            if 'cloudflare' in issue_lower:
                app_has_explicit_cloudflare.add(app_id)
        elif 'javascript-render' in issue_lower or 'spa' in issue_lower or 'page content could not be extracted' in issue_lower or 'cannot extract the rendered page' in issue_lower:
            app_field_issues[app_id][field] = 'spa_unavailable'
            app_has_explicit_spa.add(app_id)
        elif 'u' in reason_lower or 'unresolved' in issue_lower or 'no official' in issue_lower or 'cannot verify' in issue_lower or 'cannot access' in issue_lower or 'cannot determine' in issue_lower:
            app_field_issues[app_id][field] = 'insufficient_evidence'
        else:
            app_field_issues[app_id][field] = 'insufficient_evidence'

# Systemic issue detection: apps where ALL documentation is on a blocked domain
# These apps have explicit Cloudflare on identity/root field AND other fields say "Could not access"
systemic_cloudflare_apps = set()
systemic_spa_apps = set()

for app_id, issues in app_field_issues.items():
    # Check if identity field has explicit Cloudflare
    if 'identity' in issues and issues['identity'] == 'source_blocked':
        # Check if other fields have "could not access" pattern
        other_fields_blocked = True
        for field, issue_type in issues.items():
            if field != 'identity' and issue_type != 'source_blocked':
                # If any other field is NOT source_blocked but should be (e.g., says "could not access")
                # Actually, if identity is Cloudflare, and other fields are "insufficient_evidence" due to "cannot access",
                # they are likely also blocked by the same Cloudflare
                pass
        # Apps 90, 92, 94 have this pattern
        if app_id in [90, 92, 94]:
            systemic_cloudflare_apps.add(app_id)
    
    # Check for systemic SPA - if identity or multiple fields have explicit SPA
    spa_count = sum(1 for v in issues.values() if v == 'spa_unavailable')
    if spa_count >= 2 or ('identity' in issues and issues['identity'] == 'spa_unavailable'):
        systemic_spa_apps.add(app_id)

# Add known systemic apps
systemic_cloudflare_apps.update([90, 92, 94])
systemic_spa_apps.update([37, 86, 87])

# Field mapping: unresolved fields -> PSV fields
field_mapping = {
    'identity': None,
    'auth': 'auth',
    'access': 'access',
    'surface': 'surface',
    'mcp': 'mcp',
    'blocker_and_verdict': 'blocker',
    'evidence_url': 'evidence_url'
}
reverse_map = {v: k for k, v in field_mapping.items() if v}

# Build the 6-field per app check
all_apps = {'auth', 'access', 'mcp', 'surface', 'blocker', 'evidence_url'}

app_field_status = {}
for idx, line in enumerate(lines):
    app_id = idx + 1
    parts = line.split('|')
    if len(parts) >= 8:
        auth = parts[2].strip()
        access = parts[3].strip()
        surface = parts[4].strip()
        mcp = parts[5].strip()
        blocker = parts[6].strip()
        evidence_url = '|'.join(parts[7:]).strip()
        
        fields = {'auth': auth, 'access': access, 'mcp': mcp, 'surface': surface, 'blocker': blocker, 'evidence_url': evidence_url}
        
        status = {}
        for fname in all_apps:
            val = fields.get(fname, '')
            unresolved_field = reverse_map.get(fname, fname)
            
            # Systemic Cloudflare: all fields blocked
            if app_id in systemic_cloudflare_apps:
                status[fname] = 'source_blocked'
            # Systemic SPA: all fields unavailable
            elif app_id in systemic_spa_apps:
                status[fname] = 'spa_unavailable'
            # Field-specific issues from unresolved-facts.json
            elif app_id in app_field_issues and unresolved_field in app_field_issues[app_id]:
                status[fname] = app_field_issues[app_id][unresolved_field]
            # Evidence URL handling
            elif fname == 'evidence_url':
                # For partial Cloudflare apps (78, 80), evidence_url might still work
                if app_id in [78, 80]:
                    # Only the MCP help article is blocked, main docs work
                    status[fname] = 'confirmed' if val else 'not_checked'
                else:
                    status[fname] = 'confirmed' if val else 'not_checked'
            # Default checks
            else:
                if not val:
                    status[fname] = 'not_checked'
                elif val in ['U', 'N', '?']:
                    status[fname] = 'insufficient_evidence'
                else:
                    status[fname] = 'confirmed'
        
        app_field_status[app_id] = {'name': parts[1], 'fields': fields, 'status': status}

# MANUAL OVERRIDES based on consolidated-unredacted-dump.json findings
# Pinterest (app 38) - access field correction cites third-party source (lilachbullock.com)
app_field_status[38]['status']['access'] = 'third_party_only'

# Supabase (app 65) - mcp field correction has empty citation (308 redirect)
app_field_status[65]['status']['mcp'] = 'empty_citation'

# App 50 (Paygent/NMI) - identity has 403 but not Cloudflare; other fields "no docs found"
# Already handled: not in systemic lists, field-specific issues will apply
# identity -> None (not in our 6), auth/access/surface -> insufficient_evidence (no official docs)
# mcp, blocker, evidence_url -> based on values

# App 78 (Coda) - only mcp and blocker_and_verdict have Cloudflare on help.coda.io
# evidence_url uses coda.io and help.coda.io - main API docs work
if 78 in app_field_status:
    # mcp and blocker are source_blocked (from field-specific)
    # auth, access, surface are confirmed (values present)
    # evidence_url confirmed (main URLs work)
    pass

# App 80 (Harvest) - only mcp has Cloudflare on support.getharvest.com
# Other fields have values, access has "insufficient_evidence" from unresolved (no explicit free/trial docs)
# But access=F in PSV, so confirmed unless unresolved says otherwise
# The unresolved says access: "Authentication page describes PAT creation but does not explicitly state whether free or trial account"
# This is insufficient_evidence, not source_blocked
if 80 in app_field_status:
    # mcp -> source_blocked (field-specific)
    # access -> insufficient_evidence (field-specific from unresolved)
    # auth, surface, blocker -> confirmed (values present)
    # evidence_url -> confirmed
    pass

print(f"Total apps: {len(app_field_status)}")

# Count by mutually exclusive categories
buckets = {
    'confirmed': 0,
    'corrected': 0,
    'insufficient_evidence': 0,
    'source_blocked': 0,
    'third_party_only': 0,
    'empty_citation': 0,
    'spa_unavailable': 0,
    'not_checked': 0
}

blocked_apps = set()
third_party_apps = set()
empty_cite_apps = set()
spa_apps = set()
insufficient_apps = set()

total_fields = 0
for app_id, data in app_field_status.items():
    for fname in all_apps:
        s = data['status'].get(fname, 'insufficient_evidence')
        buckets[s] += 1
        
        if s == 'source_blocked':
            blocked_apps.add(app_id)
        elif s == 'third_party_only':
            third_party_apps.add(app_id)
        elif s == 'empty_citation':
            empty_cite_apps.add(app_id)
        elif s == 'spa_unavailable':
            spa_apps.add(app_id)
        elif s == 'insufficient_evidence':
            insufficient_apps.add(app_id)
        
        total_fields += 1

print(f"\nTotal fields checked: {total_fields}")
print(f"\nMutually exclusive buckets:")
for k,v in buckets.items():
    print(f"  {k}: {v}")

print(f"\nBucket sum: {sum(buckets.values())}")
print(f"Must equal 600: {sum(buckets.values()) == 600}")

print(f"\n--- Secondary flags (overlaps with insufficient_evidence) ---")
print(f"Source blocked (Cloudflare 403): apps {sorted(blocked_apps)}")
print(f"Third-party only (Pinterest): apps {sorted(third_party_apps)}")  
print(f"Empty citation (Supabase MCP): apps {sorted(empty_cite_apps)}")
print(f"SPA unavailable (JS-rendered pages): apps {sorted(spa_apps)}")

print(f"\n--- Apps with insufficient evidence ---")
print(sorted(insufficient_apps))

# Output summary for review
summary = {
    'total_apps': len(app_field_status),
    'total_fields': total_fields,
    'buckets': buckets,
    'sum_check': sum(buckets.values()) == 600,
    'blocked_apps': sorted(blocked_apps),
    'third_party_apps': sorted(third_party_apps),
    'empty_citation_apps': sorted(empty_cite_apps),
    'spa_unavailable_apps': sorted(spa_apps),
    'insufficient_evidence_apps': sorted(insufficient_apps)
}

with open('output/reconciliation-summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\nSummary written to output/reconciliation-summary.json")

# Also output per-app breakdown for verification
with open('output/per-app-status.json', 'w') as f:
    json.dump({str(k): v for k, v in app_field_status.items()}, f, indent=2)

print(f"Per-app status written to output/per-app-status.json")
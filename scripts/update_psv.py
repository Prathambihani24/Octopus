#!/usr/bin/env python3
"""Update reviewed.psv with all corrections from batch files."""

import json
from pathlib import Path

def parse_line(line):
    """Parse a PSV line handling | in URLs and blocker field"""
    parts = line.split('|')
    if len(parts) >= 8:
        return {
            'app': parts[0],
            'category': parts[1],
            'auth': parts[2],
            'access': parts[3],
            'surface': parts[4],
            'mcp': parts[5],
            'blocker_and_verdict': '|'.join(parts[6:-1]),
            'url': parts[-1]
        }
    return None

def format_line(data):
    """Format data dict to PSV line"""
    return '|'.join([
        data['app'],
        data['category'],
        data['auth'],
        data['access'],
        data['surface'],
        data['mcp'],
        data['blocker_and_verdict'],
        data['url']
    ])

def convert_auth_value(val):
    """Convert auth value to proper format (list to string)"""
    if isinstance(val, list):
        return ''.join(val)
    return str(val)

def main():
    # Read all batch files to find all "corrected" outcomes
    all_corrections = {}
    
    for batch_num in range(1, 11):
        batch_file = Path(f"/Users/pratham/Octopus/data/audit-batches/batch-{batch_num:02d}.json")
        if batch_file.exists():
            with open(batch_file) as f:
                batch = json.load(f)
                for app in batch.get("apps", []):
                    app_id = app["id"]
                    for check in app.get("checks", []):
                        if check["outcome"] == "corrected":
                            if app_id not in all_corrections:
                                all_corrections[app_id] = {}
                            all_corrections[app_id][check["field"]] = check

    # Read current reviewed.psv
    psv_file = Path("/Users/pratham/Octopus/data/reviewed.psv")
    with open(psv_file) as f:
        content = f.read()

    lines = content.strip().split('\n')
    updated_lines = []
    updates_made = 0

    for i, line in enumerate(lines, start=1):  # 1-indexed
        data = parse_line(line)
        if data is None:
            updated_lines.append(line)
            continue
        
        if i in all_corrections:
            for field, correction in all_corrections[i].items():
                new_val = correction["reviewed_value"]
                if field == "auth" or field == "access":
                    data[field] = convert_auth_value(new_val)
                else:
                    data[field] = str(new_val)
            updates_made += 1
        
        updated_lines.append(format_line(data))

    # Write back
    with open(psv_file, 'w') as f:
        f.write('\n'.join(updated_lines))

    print(f"Updated {updates_made} apps with corrections")
    print(f"Total lines: {len(updated_lines)}")
    print(f"Corrections applied to apps: {sorted(all_corrections.keys())}")

if __name__ == "__main__":
    main()
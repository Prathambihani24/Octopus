#!/usr/bin/env python3
"""Research and score documented integration paths for the assignment set."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CATEGORIES = [
    "CRM & Sales", "Support & Helpdesk", "Communications & Messaging",
    "Marketing, Ads, Email & Social", "Ecommerce", "Data, SEO & Scraping",
    "Developer, Infra & Data", "Productivity & Project Management",
    "Finance & Fintech", "AI, Research & Media",
]
AUTH = {"O": "OAuth 2.0", "K": "API key", "T": "Token", "B": "HTTP Basic",
        "S": "Signed / JWT", "H": "Other", "N": "None (local)", "U": "Unconfirmed"}
ACCESS = {"F": "Free / test route", "C": "Run locally", "P": "Paid / licensed",
          "R": "Approval / tenant gate", "U": "Unconfirmed"}
MCP = {"Y": "Vendor server documented", "U": "Vendor server unconfirmed"}
SIGNALS = {
    "auth": {
        "O": r"\boauth(?:\s+2(?:\.0)?)?\b", "K": r"\bapi[ -]?key(?:s)?\b",
        "T": r"\b(?:bearer token|access token|personal token|api token|bot token)s?\b",
        "B": r"\b(?:http basic|basic auth(?:entication)?)\b",
        "S": r"\b(?:signed requests?|jwt|hmac)\b", "H": r"\bdigest auth\b",
    },
    "access": {
        "F": r"\b(?:free plan|free tier|free trial|sandbox|test accounts?|dev stores?)\b",
        "P": r"\b(?:paid plan|enterprise plan|paid subscription|active .{0,40}license)\b",
        "R": r"\b(?:app review|admin approval|contact sales|partner approval|apply for production)\b",
        "C": r"\b(?:self-host(?:ed)?|command line tool|mmdc -i)\b",
    },
    "surface": {"rest": r"\bREST\b", "graphql": r"\bGraphQL\b", "cli": r"\b(?:CLI|mmdc)\b"},
    "mcp": {"Y": r"\b(?:MCP server|model context protocol)\b"},
}
FIELDS = ("auth", "access", "surface", "mcp")


def extract_signals(text):
    """Return document mentions as candidates, with no claim of entitlement."""
    return {field: [code for code, pattern in rules.items() if re.search(pattern, text, re.I)]
            for field, rules in SIGNALS.items()}


def baseline(seed, records):
    """A deliberately small baseline that uses the top discovery result only."""
    hit = records[0] if records else {"url": "", "signals": {}}
    signals = hit["signals"]
    return {
        "id": seed["id"], "app": seed["app"],
        "auth": sorted(signals.get("auth") or ["U"]),
        "access": (signals.get("access") or ["U"])[0],
        "surface": sorted(signals.get("surface") or ["unknown"]),
        "mcp": (signals.get("mcp") or ["U"])[0],
        "source": hit["url"],
    }


class ReadableText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def read_document(url):
    """Fetch public HTTPS documentation, without interacting with vendor APIs."""
    if urlsplit(url).scheme != "https":
        return {"url": url, "status": "skipped", "signals": {}}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ConnectorResearch/1.0"})
        with urllib.request.urlopen(request, timeout=9) as response:
            document = response.read(850_000).decode("utf-8", errors="replace")
            canonical = response.geturl()
            if "html" in response.headers.get("Content-Type", ""):
                parser = ReadableText()
                parser.feed(document)
                document = " ".join(parser.parts)
        return {"url": url, "resolved_url": canonical, "status": "read",
                "signals": extract_signals(document)}
    except (OSError, ValueError) as exc:
        return {"url": url, "status": type(exc).__name__, "signals": {}}


def load_review():
    rows = []
    with (DATA / "reviewed.psv").open(encoding="utf-8") as source:
        for app_id, row in enumerate(csv.reader(source, delimiter="|"), 1):
            name, description, auth, access, surface, mcp, caveat, links = row
            verdict = {"F": "Prototype", "C": "Local wrapper", "P": "Confirm paid access",
                       "R": "Confirm approval", "U": "Investigate"}[access]
            if auth == "U" and access not in ("P", "R"):
                verdict = "Investigate"
            rows.append({
                "id": app_id, "app": name, "category": CATEGORIES[(app_id-1)//10],
                "description": description, "auth": sorted(auth), "access": access,
                "surface": surface, "mcp": mcp, "caveat": caveat, "verdict": verdict,
                "sources": links.split(),
            })
    if len(rows) != 100 or len({r["app"] for r in rows}) != 100:
        raise ValueError("Expected 100 distinct assignment apps")
    for row in rows:
        if (not set(row["auth"]) <= AUTH.keys() or row["access"] not in ACCESS
                or row["mcp"] not in MCP or not row["sources"]):
            raise ValueError(f"Invalid review row {row['id']}")
    return rows


def compare(before, after, checks):
    original = {row["id"]: row for row in before}
    reviewed = {row["id"]: row for row in after}
    result = []
    for check in checks:
        item_id, field = check["id"], check["field"]
        old, new = original[item_id][field], reviewed[item_id][field]
        if field == "surface":
            new = sorted(extract_signals(new)["surface"] or ["unknown"])
        expected = check["expected"]
        result.append({**check, "app": reviewed[item_id]["app"], "before": old, "after": new,
                       "before_ok": old == expected, "after_ok": new == expected})
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--refresh-docs", action="store_true", help="Fetch current public docs and recompute candidate signals")
    cli.add_argument("--id", type=int, choices=range(1, 101), metavar="1..100",
                     help="Limit to one app for a quick candidate/decision comparison")
    cli.add_argument("--out", type=Path, default=ROOT / "output")
    args = cli.parse_args()
    rows = load_review()
    if args.id:
        rows = [row for row in rows if row["id"] == args.id]
    discovery = json.loads((DATA / "discovery.json").read_text(encoding="utf-8"))
    records = {row["id"]: row["results"] for row in discovery}
    if args.refresh_docs:
        with ThreadPoolExecutor(max_workers=8) as workers:
            links = list(dict.fromkeys(url for row in rows for url in row["sources"]))
            fetched = dict(zip(links, workers.map(read_document, links)))
        records = {row["id"]: [fetched[url] for url in row["sources"]] for row in rows}
    first = [baseline(row, records.get(row["id"], [])) for row in rows]
    checks = json.loads((DATA / "audit.json").read_text(encoding="utf-8"))
    present = {row["id"] for row in rows}
    evaluated = compare(first, rows, [check for check in checks if check["id"] in present])
    counts = defaultdict(Counter)
    for row in rows:
        counts[row["category"]][row["access"]] += 1
    data = {
        "apps": rows, "first_pass": first, "audit": evaluated,
        "auth_labels": AUTH, "access_labels": ACCESS, "mcp_labels": MCP,
        "summary": {"by_category": counts, "auth": Counter(code for row in rows for code in row["auth"]),
                    "access": Counter(row["access"] for row in rows), "mcp": Counter(row["mcp"] for row in rows),
                    "before_correct": sum(row["before_ok"] for row in evaluated),
                    "after_correct": sum(row["after_ok"] for row in evaluated)},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "findings.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.refresh_docs:
        (args.out / "live-signals.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} apps · {len(evaluated)} checked fields · "
          f"{data['summary']['before_correct']} → {data['summary']['after_correct']} exact matches")


if __name__ == "__main__":
    main()

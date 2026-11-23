"""Package the case study as buildless static files."""
from pathlib import Path
import json
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
findings = json.loads((ROOT / "output/findings.json").read_text(encoding="utf-8"))
human = ROOT / "data/human-audit.json"
findings["human_audit"] = json.loads(human.read_text(encoding="utf-8")) if human.exists() else []
source_url = ROOT / "data/source-url.txt"
findings["source_repo"] = source_url.read_text().strip() if source_url.exists() else ""
second = ROOT / "data/holdout-audit.json"
findings["second_audit"] = json.loads(second.read_text()) if second.exists() else None
demo = ROOT / "data/demo.json"
findings["demo"] = json.loads(demo.read_text()) if demo.exists() else None
for row in findings["apps"]:
    row["decision_group"] = "research" if row["access"] == "U" or "U" in row["auth"] else ("access" if row["access"] in ("P","R") else "prototype")
    row["prototype"] = {"F":"Documented free/test route", "C":"Local execution route", "P":"Paid access required", "R":"Approval or tenant access required", "U":"Unconfirmed"}[row["access"]]
    row["production"] = "Not verified; check entitlement, scopes and distribution"
payload = json.dumps(findings, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
template = (ROOT / "page.html").read_text(encoding="utf-8")
(dist / "index.html").write_text(template.replace("__FINDINGS__", payload), encoding="utf-8")
(dist / "findings.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False))
for name in ["demo.json", "holdout-audit.json"]:
    shutil.copyfile(ROOT / "data" / name, dist / name)
shutil.copyfile(ROOT / "README.md", dist / "README.md")
paths = ["agent.py", "test_agent.py", "data/holdout-before.json", "data/holdout-audit.json", "data/demo.json", "data/seeds.json", "README.md", "research.py", "render.py", "page.html",
         "data/discovery.json", "data/reviewed.psv", "data/audit.json",
         "output/findings.json", "dist/index.html", "dist/findings.json", "dist/README.md"]
for path in ["data/human-audit.json", "data/source-url.txt"]:
    if (ROOT / path).exists():
        paths.append(path)
with ZipFile(dist / "composio-toolkit-study.zip", "w", ZIP_DEFLATED) as archive:
    for path in paths:
        archive.write(ROOT / path, path)

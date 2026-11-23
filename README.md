# Connector readiness across 100 apps

A research case study for the Composio Product Ops Intern take-home. It prioritizes a first toolkit action and identifies which credentials or approvals stand in the way. The study covers documented feasibility. It does not use paid app accounts or make calls with live vendor credentials.

## Run it

Requires Python 3.10+ and no dependencies, model keys, or vendor accounts.

```sh
python3 research.py
python3 render.py
```

Open `dist/index.html`. The default run reconstructs the baseline and comparison from the saved discovery signals and reviewer decisions. `output/findings.json` contains all rows, baseline values, per-field audit outcomes, and aggregate counts.

```sh
python3 research.py --id 31 --out output/google-ads
python3 research.py --refresh-docs --id 31 --out output/google-ads-live
python3 research.py --refresh-docs --out output/live
```

The live command reads public documentation with bounded concurrency and re-extracts auth, access, API and MCP candidates. Inspect `live-signals.json` for fetch failures and document mentions. It is a discovery aid. A successful fetch and a keyword match alone do not justify changing a reviewed finding. Use the ordinary command to rebuild the displayed snapshot after updating a review decision.

## How this run was done

1. **Discovery.** An AI agent issued one web search per assignment app, collected source candidates, and used an intentionally simple top-result extraction baseline. `data/discovery.json` preserves the URLs and machine-extracted tags rather than full page text.
2. **Verification.** Follow-up searches targeted missing facts and confusing product names. Official developer pages and maintainer repos supplied the reviewed decisions in `data/reviewed.psv`. Fresh policy docs took precedence over stale reference pages. For example, Google Ads had a legacy header page that still described the now-sunset developer token.
3. **Audit.** `data/audit.json` records the expected answer, official source, and reasoning for each selected field. The script scores exact auth sets or exact access, surface, or MCP labels. This is a targeted correction demonstration on the same audited fields. It is not a blind estimate of correctness across all 100. Applicant checks, if included, are attributed separately on the site.
4. **Decision.** Group the earliest evidenced build path by category. The HTML makes the review notes, ordinary proof links, and machine-readable results available from the same page.

OAuth, API key, opaque token, Basic, signed/JWT, other and local no-auth are overlapping tags. For example, a vendor can use an API key as its Basic credential. Auth is for the scoped API or CLI, which may differ from MCP login. “Free / test route” means an evidenced starting path and says nothing about live entitlement. The other routes are local, paid or licensed, an approval or tenant gate, and unconfirmed. If a vendor documents an MCP server that exposes its own tool surface or maintains its implementation, it is counted as a vendor server. An unconfirmed MCP status does not assert absence.

## Files

- `research.py` — candidate extraction, live documentation refresh, normalization, and scoring.
- `data/reviewed.psv` — reviewed app matrix and evidence links, one row per app in assignment order.
- `data/discovery.json` — reproducible top-result baseline inputs.
- `data/audit.json` — official evidence and expected values for the audit sample.
- `render.py`, `page.html` — static report generator and template.
- `dist/` — deployable case study and downloads.

## New app discovery (v2)

Live case study: https://composio-connector-study.vercel.app/
Source: https://github.com/Prathambihani24/Octopus

```sh
python3 agent.py --app Resend --website https://resend.com/docs --max-pages 8 --out output/new-app
python3 agent.py --batch data/seeds.json --max-pages 8 --out output/batch
python3 -m unittest test_agent.py
```

`agent.py` is a deterministic research pipeline. It starts at the supplied official website/docs URL and `/llms.txt`, follows relevant links within that hostname and its subdomains, and extracts candidate evidence for auth, access, surface and MCP. It discovers documents without loading reviewed answers. Domain and product identity are supplied by the operator; this version does not perform open-web search or infer semantic truth with a model. Alternate documentation domains require a separate seed.

Results include a local HTML report, JSON evidence, timestamps, document hashes, attempted/read page counts, elapsed time, and explicit missing fields. Full fetched documents are saved locally for inspection, not deployed. Successful fetches are cached under the output parent; use `--refresh` to re-fetch. Runs use at most four concurrent requests and a configurable 2–30 page budget per app. Model usage is zero tokens. A page mentioning OAuth or a sandbox is only a candidate, never automatic proof of entitlement. The pipeline leaves production readiness unconfirmed and requires human/assistant review of negation, product scope, API breadth and useful actions. It does not modify the reviewed matrix automatically.

`data/demo.json` is the actual eight-page Resend run, an app outside the assignment set. The live page generates a shell-safe local run command; it is not a hosted research execution backend. No Composio SDK/MCP integration is claimed.

## Second verification pass

Ten apps outside the first correction sample were selected before opening the fresh sources. Their original rows are retained in `data/holdout-before.json`; findings are in `data/holdout-audit.json`. This checks auth-set completeness only. Five original sets matched and five required additions. The corrected sets then match the reviewed expected sets. This is a second assistant review, not a blind independent evaluation or an estimate of total dataset accuracy. It exposes real omissions in Plain, Freshdesk, Mailchimp, Apify and GitHub. Applicant checks remain pending.

The decision panel groups feasibility using explicit access/auth labels. Prototype candidates have a documented free/test/local route and known auth. Paid or approval routes need access work. Unknown auth or access goes to research. Customer demand and existing Composio coverage remain unmeasured, so this is not a revenue-ranked roadmap. No production integration is represented as tested.

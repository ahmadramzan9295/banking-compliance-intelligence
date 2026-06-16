# Global Banking Compliance & Risk Intelligence System

A multi-agent backend that produces **deterministic, citation-backed, audit-logged**
regulatory compliance analysis across banking jurisdictions (sample domain: Basel III
capital and liquidity requirements for US, EU, UK). Built as a reference architecture
for an enterprise compliance/risk intelligence platform.

> **Data note:** the regulatory rules in `app/data/sample_sources/` are simplified,
> illustrative datasets for demonstration purposes — not a live regulatory feed.
> In production, `ingestion_agent.py` is the single point you'd swap to pull from
> real regulator APIs, document stores, or a vendor compliance feed.

---

## 1. System Architecture

```
Client (HTTP / CLI)
        │
        ▼
   Orchestrator  ── fixed, deterministic agent sequence, no LLM sampling
        │
        ├─ Agent 1: Data Ingestion Agent        (pulls raw source docs per jurisdiction)
        ├─ Agent 2: Normalization Agent         (standardizes into canonical record shape)
        ├─ Agent 3: Validation Agent            (schema + business rule checks, rejects bad records)
        ├─ Agent 4: Contradiction Detection      (cross-jurisdiction rule divergence)
        ├─ Agent 5: Confidence Scoring Agent     (reliability + consistency + cross-validation)
        └─ Agent 6: Report Generation Agent      (assembles + re-validates strict JSON output)
        │
        ▼
   Audit Logger  ── input/output hashing, content_hash for reproducibility, JSONL trail
```

Design principles:

- **Determinism first.** No agent uses randomness or LLM sampling. Every confidence
  score, contradiction flag, and summary sentence is a pure function of the input
  data, so re-running the same request against unchanged sources reproduces an
  identical `content_hash` (verified in `tests/test_pipeline.py`).
- **Strict output contract.** `app/schemas/output_schema.py` defines the canonical
  JSON Schema. The Report Generation Agent validates against it before returning —
  a non-conformant payload never leaves the system.
- **Fail loud, not silent.** Invalid records are rejected with explicit reasons
  (logged + recorded in the audit trail), not dropped quietly. Unknown jurisdictions
  raise a typed `IngestionError` the API layer converts to a clean 404.
- **Extensible by registry, not by code change.** Adding a jurisdiction or a new
  topic means registering a data source in `jurisdiction_registry.py` — no agent
  logic changes.

---

## 2. Code Structure

```
banking-compliance-intelligence/
├── app/
│   ├── main.py                       # FastAPI app (HTTP layer)
│   ├── orchestrator.py               # Deterministic 6-agent pipeline driver
│   ├── agents/
│   │   ├── base.py                   # BaseAgent: run() timing/logging contract
│   │   ├── ingestion_agent.py        # Agent 1
│   │   ├── normalization_agent.py    # Agent 2
│   │   ├── validation_agent.py       # Agent 3
│   │   ├── contradiction_agent.py    # Agent 4
│   │   ├── confidence_agent.py       # Agent 5
│   │   └── report_agent.py           # Agent 6
│   ├── schemas/
│   │   ├── output_schema.py          # Canonical JSON Schema + validator
│   │   └── api_models.py             # Pydantic request/response models
│   ├── registry/
│   │   └── jurisdiction_registry.py  # Extensible jurisdiction/source registry
│   ├── audit/
│   │   └── audit_logger.py           # Audit trail: hashing, JSONL, lookup
│   ├── utils/
│   │   └── logging_config.py         # Centralized logger factory
│   └── data/sample_sources/          # Sample regulatory datasets (US/EU/UK)
├── tests/test_pipeline.py            # 13 unit tests (schema, agents, reproducibility)
├── run_demo.py                       # CLI runner (no server required)
├── sample_output.json                # Example strict-format output
├── requirements.txt
└── README.md
```

---

## 3. Sample Implementation Highlights

**Validation Layer** (`app/agents/validation_agent.py`) — rejects records missing
required fields, with out-of-range values, unknown jurisdiction codes, or malformed
dates, without crashing the pipeline:

```python
def _validate_record(self, record):
    errors = []
    for field in ["jurisdiction", "rule_key", "title", "value", "unit", "text"]:
        if record.get(field) in (None, ""):
            errors.append(f"missing or empty required field '{field}'")
    if record.get("unit") == "percent" and not (0.0 <= record["value"] <= 200.0):
        errors.append(f"value {record['value']} outside plausible percent range")
    return errors
```

**Contradiction Detection** (`app/agents/contradiction_agent.py`) — compares the
primary jurisdiction's rules against every peer jurisdiction sharing a `rule_key`,
flags divergence beyond a 1% tolerance, with deterministic severity banding:

```python
def _severity_for_delta(delta_pct):
    if delta_pct < 10.0:  return "low"
    if delta_pct < 30.0:  return "medium"
    return "high"
```

**Confidence Scoring** (`app/agents/confidence_agent.py`) — weighted, explainable
score with components returned alongside the final number for auditability:

```python
score = (0.40 * source_reliability_avg
       + 0.35 * consistency_score        # 1 - severity-weighted contradiction penalty
       + 0.25 * cross_validation_score)  # fraction of rules checkable against peers
```

**Audit Logging** (`app/audit/audit_logger.py`) — every run is appended to
`logs/audit_trail.jsonl` with:

```json
{
  "audit_log_id": "AUD-...",
  "input_hash": "sha256...",
  "output_hash": "sha256...",
  "content_hash": "sha256...",   // excludes timestamp/audit_log_id — proves reproducibility
  "stage_timings": [...],
  "rejected_records": [...]
}
```

---

## 4. Sample JSON Output

See `sample_output.json`. Abbreviated:

```json
{
  "jurisdiction": "US",
  "regulation_topic": "basel_iii_capital_requirements",
  "summary": "US maintains 4 core requirement(s)... 2 cross-jurisdiction divergence(s) were identified (2 high, 0 medium, 0 low severity)...",
  "key_rules": [
    { "rule_key": "cet1_minimum_ratio", "title": "Common Equity Tier 1 Minimum Ratio", "value": 4.5, "unit": "percent", "description": "..." }
  ],
  "contradictions": [
    {
      "rule_key": "supplementary_leverage_ratio",
      "jurisdiction_a": "US", "value_a": 5.0,
      "jurisdiction_b": "EU", "value_b": 3.0,
      "severity": "high",
      "description": "US requires 5.0% ... while EU requires 3.0% ... a 40.0% relative divergence."
    }
  ],
  "confidence_score": 0.875,
  "citations": [
    { "source": "US regulatory source", "regulator": "Federal Reserve / OCC", "publication_date": "2025-01-10", "reliability": 0.95 }
  ],
  "version": "1.0.0",
  "timestamp": "2026-06-16T08:43:29.253523+00:00",
  "audit_log_id": "AUD-e565b64a-2b9c-47a2-8496-b43ac31d4ca8"
}
```

---

## 5. How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run via CLI (no server needed) — prints the structured JSON to stdout
python run_demo.py --jurisdiction US
python run_demo.py --jurisdiction EU
python run_demo.py --jurisdiction UK
python run_demo.py --list-jurisdictions

# 3. Or run the API server
uvicorn app.main:app --reload --port 8000

# Then call it:
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"jurisdiction": "US", "regulation_topic": "basel_iii_capital_requirements"}'

curl http://localhost:8000/api/v1/jurisdictions
curl http://localhost:8000/api/v1/audit/AUD-<id-from-a-previous-run>

# 4. Run the test suite
python -m unittest tests/test_pipeline.py -v
```

This repository has been executed and tested in a sandboxed environment as part of
generating this deliverable — `run_demo.py` and the full unit test suite (13 tests:
schema validation, record validation, contradiction detection, confidence scoring,
and full-pipeline reproducibility) pass end to end.

---

## 6. Extending the System

**Add a jurisdiction** — register a new source file, no agent code changes:
```python
from app.registry.jurisdiction_registry import registry
registry.register_source("SG", "basel_iii_capital_requirements",
                          "app/data/sample_sources/sg_basel_iii.json")
```

**Add a new topic** (e.g. AML/KYC thresholds, capital stress testing) — create
source files following the same `{jurisdiction, regulator, rules: [...]}` shape and
register them under a new topic key. Agents are topic-agnostic.

**Swap in a real data feed** — replace `_load_source()` in `ingestion_agent.py` with
an API/database call; everything downstream is unaffected.

---

## 7. Loom Demo Script (1–2 min)

> **[0:00–0:15] Hook + framing**
> "This is a multi-agent regulatory intelligence system for global banking compliance —
> think Basel III capital requirements across US, EU, and UK regulators. It's built
> the way a financial institution would actually need it: deterministic, schema-validated,
> and fully audit-logged."

> **[0:15–0:45] Architecture walkthrough**
> "Six agents run in a fixed sequence — Ingestion, Normalization, Validation,
> Contradiction Detection, Confidence Scoring, and Report Generation. [Show the
> folder structure.] Each agent has a single responsibility, so you can swap, say,
> the ingestion source for a live regulator API without touching anything else.
> There's no LLM sampling anywhere in here — every output is a pure function of
> the input data, which is the whole point for a compliance use case."

> **[0:45–1:15] Live run + output**
> "Let me run it for the US." [run `python run_demo.py --jurisdiction US`] "You get
> back strict JSON: key rules, citations back to the source regulator, and — this is
> the interesting part — contradictions. The system flagged that the US leverage
> ratio requirement is 40% higher than the EU's equivalent rule. That's exactly the
> kind of cross-jurisdiction divergence a compliance team needs surfaced automatically."

> **[1:15–1:45] Confidence + audit trail**
> "Confidence score here is 0.875, and it's fully explainable — it's a weighted
> combination of source reliability, internal consistency, and cross-validation
> coverage, not a black box. And every single run gets logged to an audit trail
> with input/output hashes, so you can prove reproducibility to a regulator or
> auditor after the fact."

> **[1:45–2:00] Close**
> "It's production-style: typed errors, schema rejection instead of silent failure,
> unit tests covering the agents and the full pipeline, and a clean extension point
> for new jurisdictions or data sources. Happy to walk through any part of the
> codebase in more depth."

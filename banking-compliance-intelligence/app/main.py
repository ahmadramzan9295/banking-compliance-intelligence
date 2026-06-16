"""
FastAPI Application Entrypoint
--------------------------------
Run with:
    uvicorn app.main:app --reload --port 8000

Endpoints:
    POST /api/v1/analyze        -> run the full multi-agent pipeline
    GET  /api/v1/audit/{id}     -> retrieve a past audit trail entry
    GET  /api/v1/jurisdictions  -> list registered jurisdictions/topics
    GET  /health                -> liveness probe
"""

from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.orchestrator import RegulatoryIntelligenceOrchestrator
from app.registry.jurisdiction_registry import registry
from app.audit.audit_logger import AuditLogger
from app.schemas.api_models import AnalyzeRequest, AnalyzeResponse
from app.schemas.output_schema import SchemaValidationError
from app.agents.ingestion_agent import IngestionError

app = FastAPI(
    title="Global Banking Compliance & Risk Intelligence System",
    description=(
        "Multi-agent regulatory intelligence pipeline producing deterministic, "
        "citation-backed, audit-logged compliance analysis across jurisdictions."
    ),
    version="1.0.0",
)

orchestrator = RegulatoryIntelligenceOrchestrator()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/jurisdictions")
def list_jurisdictions(topic: str = "basel_iii_capital_requirements"):
    return {"topic": topic, "jurisdictions": registry.list_jurisdictions(topic)}


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    try:
        report = orchestrator.run(
            jurisdiction=req.jurisdiction, regulation_topic=req.regulation_topic
        )
        return report
    except IngestionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SchemaValidationError as exc:
        raise HTTPException(status_code=500, detail={"schema_errors": exc.errors})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/v1/audit/{audit_log_id}")
def get_audit_entry(audit_log_id: str):
    entry = AuditLogger.lookup(audit_log_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"audit_log_id '{audit_log_id}' not found")
    return JSONResponse(content=entry)

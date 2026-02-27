"""REST API surface for GST reconciliation platform."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from gst_graph_engine import GSTReconciliationEngine, RiskLevel, build_demo_graph

app = FastAPI(title="GST KG Reconciliation API", version="2.0.0")
engine = GSTReconciliationEngine(build_demo_graph())


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gst-kg-reconciliation"}


@app.get("/api/reconciliation/invoices")
def list_reconciliation() -> list[dict]:
    return [engine.result_dict(r) for r in engine.reconcile_all_invoices()]


@app.get("/api/reconciliation/invoices/{invoice_id}")
def get_reconciliation(invoice_id: str) -> dict:
    try:
        return engine.result_dict(engine.reconcile_invoice(invoice_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/audit/{invoice_id}")
def get_audit(invoice_id: str) -> dict:
    try:
        result = engine.reconcile_invoice(invoice_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "invoice_id": invoice_id,
        "narrative": engine.generate_audit_narrative(result),
        "trail": result.trail,
        "mismatches": [m.__dict__ for m in result.mismatches],
    }


@app.get("/api/dashboard/summary")
def dashboard_summary() -> dict:
    return engine.build_dashboard_summary().__dict__


@app.get("/api/dashboard/view")
def dashboard_view(
    min_risk: str | None = Query(default=None),
    supplier_gstin: str | None = Query(default=None),
    only_mismatch: bool = Query(default=False),
) -> dict:
    level = RiskLevel(min_risk) if min_risk else None
    return engine.build_dashboard_view(min_risk=level, supplier_gstin=supplier_gstin, only_mismatch=only_mismatch)


@app.get("/api/vendors/risk")
def vendor_risk() -> list[dict]:
    return [engine.vendor_profile_dict(v) for v in engine.predict_vendor_compliance_risk()]

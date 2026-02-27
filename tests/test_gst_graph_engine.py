import networkx as nx

from api import dashboard_view, vendor_risk
from gst_graph_engine import (
    EntityType,
    GSTDataIngestion,
    GSTKnowledgeGraph,
    GSTReconciliationEngine,
    RiskLevel,
    build_demo_graph,
)


def test_networkx_graph_schema_and_ingestion():
    graph = GSTKnowledgeGraph()
    ingestion = GSTDataIngestion(graph)
    ingestion.ingest_taxpayer("27ABCDE1234F1Z5", "Demo Co")
    ingestion.ingest_invoices([
        {"invoice_id": "INV-X", "supplier_gstin": "27ABCDE1234F1Z5", "tax_amount": 1000.0}
    ])

    assert isinstance(graph.graph, nx.MultiDiGraph)
    assert graph.node("INV-X").entity_type == EntityType.INVOICE
    assert any(e.relation == "ISSUED_BY_GSTIN" for e in graph.neighbors("INV-X"))


def test_reconciliation_and_audit_flow():
    engine = GSTReconciliationEngine(build_demo_graph())
    matched = engine.reconcile_invoice("INV-1001")
    mismatch = engine.reconcile_invoice("INV-2001")

    assert matched.status == "MATCHED"
    assert matched.risk_level == RiskLevel.LOW
    assert mismatch.status == "MISMATCH"
    assert mismatch.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert "prioritized" in engine.generate_audit_narrative(mismatch)


def test_dashboard_vendor_model_and_api_view():
    engine = GSTReconciliationEngine(build_demo_graph())
    view = engine.build_dashboard_view(min_risk=RiskLevel.HIGH, only_mismatch=True)
    profiles = engine.predict_vendor_compliance_risk()

    assert set(view["visible_invoices"]) == {"INV-2001", "INV-3001"}
    assert profiles[0].supplier_gstin == "29PQRSX5678L1Z2"

    api_view = dashboard_view(min_risk="HIGH", only_mismatch=True)
    api_vendors = vendor_risk()
    assert "summary" in api_view
    assert len(api_vendors) >= 1

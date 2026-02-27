"""GST reconciliation platform with graph-native traversal, risk analytics, and explainable outputs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence

import networkx as nx


class EntityType(str, Enum):
    TAXPAYER = "TAXPAYER"
    GSTIN = "GSTIN"
    INVOICE = "INVOICE"
    IRN = "IRN"
    PURCHASE_REGISTER = "PURCHASE_REGISTER"
    RETURN_GSTR1 = "RETURN_GSTR1"
    RETURN_GSTR2B = "RETURN_GSTR2B"
    RETURN_GSTR3B = "RETURN_GSTR3B"
    TAX_PAYMENT = "TAX_PAYMENT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Node:
    node_id: str
    entity_type: EntityType
    attrs: Dict[str, object]


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str
    attrs: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MismatchDetail:
    code: str
    message: str
    root_cause: str
    severity_weight: int


@dataclass
class ReconciliationResult:
    invoice_id: str
    supplier_gstin: str
    status: str
    risk_level: RiskLevel
    risk_score: float
    mismatches: List[MismatchDetail]
    trail: List[str]


@dataclass
class VendorRiskProfile:
    supplier_gstin: str
    invoice_count: int
    mismatch_rate: float
    avg_invoice_risk_score: float
    graph_pattern_flags: List[str]
    predicted_risk: RiskLevel
    predictive_score: float
    feature_vector: Dict[str, float]
    explanation: str


@dataclass
class DashboardSummary:
    total_invoices: int
    matched_invoices: int
    mismatched_invoices: int
    total_itc_exposure: float
    risk_distribution: Dict[str, int]
    vendor_scores: Dict[str, float]


class GSTKnowledgeGraph:
    """NetworkX MultiDiGraph wrapper for GST knowledge graph operations."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    def add_node(self, node: Node) -> None:
        self.graph.add_node(node.node_id, entity_type=node.entity_type.value, attrs=node.attrs)

    def add_edge(self, edge: Edge) -> None:
        if not self.graph.has_node(edge.source) or not self.graph.has_node(edge.target):
            missing = [n for n in [edge.source, edge.target] if not self.graph.has_node(n)]
            raise KeyError(f"Cannot create edge with missing nodes: {missing}")
        self.graph.add_edge(edge.source, edge.target, relation=edge.relation, attrs=edge.attrs)

    def node(self, node_id: str) -> Optional[Node]:
        if not self.graph.has_node(node_id):
            return None
        data = self.graph.nodes[node_id]
        return Node(node_id=node_id, entity_type=EntityType(data["entity_type"]), attrs=dict(data.get("attrs", {})))

    def neighbors(self, node_id: str, relation: Optional[str] = None) -> List[Edge]:
        if not self.graph.has_node(node_id):
            return []
        out: List[Edge] = []
        for _, target, _, data in self.graph.out_edges(node_id, keys=True, data=True):
            rel = str(data.get("relation"))
            if relation is None or rel == relation:
                out.append(Edge(node_id, rel, target, dict(data.get("attrs", {}))))
        return out

    def invoice_ids(self) -> List[str]:
        return sorted(
            [node_id for node_id, data in self.graph.nodes(data=True) if data.get("entity_type") == EntityType.INVOICE.value]
        )

    def relation_count(self, relation: str) -> int:
        count = 0
        for node_id in self.graph.nodes():
            for _, _, _, data in self.graph.out_edges(node_id, keys=True, data=True):
                if data.get("relation") == relation:
                    count += 1
        return count


class GSTDataIngestion:
    def __init__(self, graph: GSTKnowledgeGraph):
        self.graph = graph

    def ingest_taxpayer(self, gstin: str, legal_name: str) -> None:
        taxpayer_id = f"TAXPAYER::{gstin}"
        gstin_id = f"GSTIN::{gstin}"
        self.graph.add_node(Node(taxpayer_id, EntityType.TAXPAYER, {"legal_name": legal_name}))
        self.graph.add_node(Node(gstin_id, EntityType.GSTIN, {"gstin": gstin}))
        self.graph.add_edge(Edge(taxpayer_id, "HAS_GSTIN", gstin_id))

    def ingest_invoices(self, rows: Iterable[Dict[str, object]]) -> None:
        for row in rows:
            invoice_id = str(row["invoice_id"])
            supplier_gstin = str(row["supplier_gstin"])
            self.graph.add_node(
                Node(
                    invoice_id,
                    EntityType.INVOICE,
                    {
                        "supplier_gstin": supplier_gstin,
                        "tax_amount": float(row["tax_amount"]),
                        "invoice_value": float(row.get("invoice_value", 0.0)),
                    },
                )
            )
            self.graph.add_edge(Edge(invoice_id, "ISSUED_BY_GSTIN", f"GSTIN::{supplier_gstin}"))

    def ingest_gstr1(self, rows: Iterable[Dict[str, object]]) -> None:
        for row in rows:
            invoice_id = str(row["invoice_id"])
            node_id = f"GSTR1::{row['period']}::{invoice_id}"
            self.graph.add_node(Node(node_id, EntityType.RETURN_GSTR1, {"tax_amount": float(row["tax_amount"])}))
            self.graph.add_edge(Edge(invoice_id, "DECLARED_IN_GSTR1", node_id))

    def ingest_gstr2b(self, rows: Iterable[Dict[str, object]]) -> None:
        for row in rows:
            invoice_id = str(row["invoice_id"])
            node_id = f"GSTR2B::{row['period']}::{invoice_id}"
            self.graph.add_node(Node(node_id, EntityType.RETURN_GSTR2B, {"tax_amount": float(row["tax_amount"])}))
            self.graph.add_edge(Edge(invoice_id, "REFLECTED_IN_GSTR2B", node_id))

    def ingest_purchase_register(self, rows: Iterable[Dict[str, object]]) -> None:
        for row in rows:
            invoice_id = str(row["invoice_id"])
            node_id = f"PR::{row['period']}::{invoice_id}"
            self.graph.add_node(Node(node_id, EntityType.PURCHASE_REGISTER, {"booked_itc": float(row["tax_amount"])}))
            self.graph.add_edge(Edge(invoice_id, "BOOKED_IN_PURCHASE_REGISTER", node_id))

    def ingest_einvoice(self, rows: Iterable[Dict[str, object]]) -> None:
        for row in rows:
            invoice_id = str(row["invoice_id"])
            node_id = f"IRN::{row['irn']}"
            self.graph.add_node(Node(node_id, EntityType.IRN, {"irn_valid": bool(row.get("irn_valid", True))}))
            self.graph.add_edge(Edge(invoice_id, "HAS_IRN", node_id))


class GSTReconciliationEngine:
    def __init__(self, graph: GSTKnowledgeGraph):
        self.graph = graph

    def reconcile_invoice(self, invoice_id: str) -> ReconciliationResult:
        invoice = self._require_node(invoice_id, EntityType.INVOICE)
        supplier_gstin = str(invoice.attrs.get("supplier_gstin", "UNKNOWN"))
        mismatches: List[MismatchDetail] = []
        trail = [f"Start traversal at {invoice_id} for GSTIN {supplier_gstin}."]

        self._validate_link(invoice_id, "ISSUED_BY_GSTIN", EntityType.GSTIN, trail, mismatches, "GSTIN_LINK_MISSING", "Supplier GSTIN linkage missing", "Master data quality", 20)
        self._validate_link(invoice_id, "HAS_IRN", EntityType.IRN, trail, mismatches, "IRN_MISSING", "IRN missing for invoice", "e-Invoice non-compliance", 25)
        self._validate_link(invoice_id, "BOOKED_IN_PURCHASE_REGISTER", EntityType.PURCHASE_REGISTER, trail, mismatches, "PR_MISSING", "Invoice missing in purchase register", "Accounting capture gap", 25)

        gstr1 = self._first_target(invoice_id, "DECLARED_IN_GSTR1")
        gstr2b = self._first_target(invoice_id, "REFLECTED_IN_GSTR2B")
        if gstr1:
            trail.append(f"Found GSTR-1 node {gstr1.node_id}.")
        else:
            mismatches.append(MismatchDetail("GSTR1_MISSING", "Invoice not declared in GSTR-1", "Supplier filing gap", 35))
            trail.append("No GSTR-1 declaration found.")

        if gstr2b:
            trail.append(f"Found GSTR-2B node {gstr2b.node_id}.")
        else:
            mismatches.append(MismatchDetail("GSTR2B_MISSING", "Invoice absent in GSTR-2B", "Recipient reflection gap", 30))
            trail.append("No GSTR-2B reflection found.")

        chain_ok, payment = self._validate_payment_chain(invoice_id)
        if chain_ok and payment:
            trail.append(f"Validated chain INVOICE->GSTR1->GSTR3B->PAYMENT ({payment.node_id}).")
        else:
            mismatches.append(MismatchDetail("TAX_CHAIN_BROKEN", "Invoice-to-tax-payment chain broken", "Liability-payment continuity gap", 50))
            trail.append("Multi-hop chain validation failed.")
            payment = None

        amount_issue = self._amount_consistency_check(invoice, gstr1, gstr2b, payment)
        if amount_issue:
            mismatches.append(amount_issue)
            trail.append(f"Amount consistency failed: {amount_issue.message}.")
        else:
            trail.append("Amounts are consistent across invoice/returns/payment.")

        score = self._risk_score(invoice, mismatches)
        level = self._risk_level_from_score(score)
        status = "MATCHED" if not mismatches else "MISMATCH"
        trail.append(f"Completed with {status}, risk={level.value}, score={score:.1f}.")

        return ReconciliationResult(invoice_id, supplier_gstin, status, level, score, mismatches, trail)

    def reconcile_all_invoices(self) -> List[ReconciliationResult]:
        return [self.reconcile_invoice(i) for i in self.graph.invoice_ids()]

    def build_dashboard_summary(self, results: Optional[Iterable[ReconciliationResult]] = None) -> DashboardSummary:
        rows = list(results) if results is not None else self.reconcile_all_invoices()
        dist = {r.value: 0 for r in RiskLevel}
        vendor_scores: Dict[str, List[float]] = defaultdict(list)
        exposure = 0.0

        for row in rows:
            dist[row.risk_level.value] += 1
            vendor_scores[row.supplier_gstin].append(row.risk_score)
            if row.status == "MISMATCH":
                n = self.graph.node(row.invoice_id)
                if n:
                    exposure += float(n.attrs.get("tax_amount", 0.0))

        return DashboardSummary(
            total_invoices=len(rows),
            matched_invoices=sum(1 for r in rows if r.status == "MATCHED"),
            mismatched_invoices=sum(1 for r in rows if r.status == "MISMATCH"),
            total_itc_exposure=round(exposure, 2),
            risk_distribution=dist,
            vendor_scores={k: round(sum(v) / len(v), 2) for k, v in vendor_scores.items()},
        )

    def build_dashboard_view(
        self,
        results: Optional[Iterable[ReconciliationResult]] = None,
        min_risk: Optional[RiskLevel] = None,
        supplier_gstin: Optional[str] = None,
        only_mismatch: bool = False,
    ) -> Dict[str, object]:
        rows = list(results) if results is not None else self.reconcile_all_invoices()
        filtered = rows
        if supplier_gstin:
            filtered = [r for r in filtered if r.supplier_gstin == supplier_gstin]
        if min_risk:
            threshold = self._risk_rank(min_risk)
            filtered = [r for r in filtered if self._risk_rank(r.risk_level) >= threshold]
        if only_mismatch:
            filtered = [r for r in filtered if r.status == "MISMATCH"]

        return {
            "filters": {
                "supplier_gstin": supplier_gstin or "ALL",
                "min_risk": min_risk.value if min_risk else "ALL",
                "only_mismatch": only_mismatch,
            },
            "summary": asdict(self.build_dashboard_summary(filtered)),
            "visible_invoices": [r.invoice_id for r in filtered],
            "rows": [self.result_dict(r) for r in filtered],
            "top_vendors": [self.vendor_profile_dict(v) for v in self.predict_vendor_compliance_risk(filtered)[:5]],
        }

    def predict_vendor_compliance_risk(self, historical_results: Optional[Iterable[ReconciliationResult]] = None) -> List[VendorRiskProfile]:
        rows = list(historical_results) if historical_results is not None else self.reconcile_all_invoices()
        grouped: Dict[str, List[ReconciliationResult]] = defaultdict(list)
        for row in rows:
            grouped[row.supplier_gstin].append(row)

        graph_pressure = self._graph_pressure_score()
        profiles: List[VendorRiskProfile] = []
        for gstin, items in sorted(grouped.items()):
            mismatch_rate = sum(1 for i in items if i.status == "MISMATCH") / len(items)
            avg_score = sum(i.risk_score for i in items) / len(items)

            chain_break_ratio = self._mismatch_ratio(items, "TAX_CHAIN_BROKEN")
            irn_gap_ratio = self._mismatch_ratio(items, "IRN_MISSING")
            filing_gap_ratio = self._mismatch_ratio(items, "GSTR1_MISSING")

            feature_vector = {
                "mismatch_rate": round(mismatch_rate, 4),
                "avg_score_norm": round(avg_score / 100.0, 4),
                "chain_break_ratio": round(chain_break_ratio, 4),
                "irn_gap_ratio": round(irn_gap_ratio, 4),
                "filing_gap_ratio": round(filing_gap_ratio, 4),
                "graph_pressure": round(graph_pressure, 4),
            }

            predictive_score = (
                40 * mismatch_rate
                + 25 * (avg_score / 100.0)
                + 15 * chain_break_ratio
                + 8 * irn_gap_ratio
                + 8 * filing_gap_ratio
                + 4 * graph_pressure
            ) * 100 / 100
            predictive_score = min(100.0, round(predictive_score, 2))
            risk = self._risk_level_from_score(predictive_score)

            flags: List[str] = []
            if chain_break_ratio >= 0.3:
                flags.append("Recurring liability-payment chain breaks")
            if irn_gap_ratio >= 0.2:
                flags.append("Recurring IRN non-compliance")
            if filing_gap_ratio >= 0.3:
                flags.append("Recurring supplier filing gaps")

            profiles.append(
                VendorRiskProfile(
                    supplier_gstin=gstin,
                    invoice_count=len(items),
                    mismatch_rate=mismatch_rate,
                    avg_invoice_risk_score=avg_score,
                    graph_pattern_flags=flags,
                    predicted_risk=risk,
                    predictive_score=predictive_score,
                    feature_vector=feature_vector,
                    explanation=(
                        f"score={predictive_score}, mismatch_rate={mismatch_rate:.0%}, avg_score={avg_score:.1f}, "
                        f"chain_break={chain_break_ratio:.0%}, irn_gap={irn_gap_ratio:.0%}, filing_gap={filing_gap_ratio:.0%}"
                    ),
                )
            )

        return sorted(profiles, key=lambda p: p.predictive_score, reverse=True)

    def generate_audit_narrative(self, result: ReconciliationResult) -> str:
        if result.status == "MATCHED":
            return (
                f"Invoice {result.invoice_id} reconciled successfully with risk {result.risk_level.value} "
                f"(score {result.risk_score:.1f})."
            )
        reasons = "; ".join(f"{m.code}: {m.root_cause}" for m in result.mismatches)
        return (
            f"Invoice {result.invoice_id} failed reconciliation with {len(result.mismatches)} mismatch(es): {reasons}. "
            f"Risk is {result.risk_level.value} (score {result.risk_score:.1f}) and should be prioritized for audit."
        )

    def result_dict(self, result: ReconciliationResult) -> Dict[str, object]:
        out = asdict(result)
        out["risk_level"] = result.risk_level.value
        out["mismatches"] = [asdict(m) for m in result.mismatches]
        return out

    def vendor_profile_dict(self, profile: VendorRiskProfile) -> Dict[str, object]:
        out = asdict(profile)
        out["predicted_risk"] = profile.predicted_risk.value
        return out

    def _validate_payment_chain(self, invoice_id: str) -> tuple[bool, Optional[Node]]:
        path = self._find_relation_path(invoice_id, ["DECLARED_IN_GSTR1", "SUMMARIZED_IN_GSTR3B", "SETTLED_BY_PAYMENT"])
        if not path:
            return False, None
        return True, self.graph.node(path[-1])

    def _find_relation_path(self, start: str, relations: Sequence[str]) -> Optional[List[str]]:
        current = start
        path = [start]
        for relation in relations:
            edges = self.graph.neighbors(current, relation)
            if not edges:
                return None
            current = edges[0].target
            path.append(current)
        return path

    def _first_target(self, source_id: str, relation: str) -> Optional[Node]:
        edges = self.graph.neighbors(source_id, relation)
        return self.graph.node(edges[0].target) if edges else None

    def _validate_link(self, source_id: str, relation: str, expected: EntityType, trail: List[str], mismatches: List[MismatchDetail], code: str, message: str, cause: str, severity: int) -> None:
        target = self._first_target(source_id, relation)
        if target and target.entity_type == expected:
            trail.append(f"Validated {relation} to {target.node_id}.")
            return
        trail.append(f"Missing/invalid {relation} link.")
        mismatches.append(MismatchDetail(code, message, cause, severity))

    def _amount_consistency_check(self, invoice: Node, gstr1: Optional[Node], gstr2b: Optional[Node], payment: Optional[Node]) -> Optional[MismatchDetail]:
        values = [
            float(invoice.attrs.get("tax_amount", 0.0)),
            float(gstr1.attrs.get("tax_amount", 0.0)) if gstr1 else 0.0,
            float(gstr2b.attrs.get("tax_amount", 0.0)) if gstr2b else 0.0,
            float(payment.attrs.get("tax_amount", 0.0)) if payment else 0.0,
        ]
        invoice_tax = values[0]
        if any(v <= 0 for v in values):
            return MismatchDetail("AMOUNT_DATA_GAP", "Tax amount unavailable across linked nodes", "Data completeness issue", 15)
        tolerance = max(1.0, invoice_tax * 0.01)
        if any(abs(invoice_tax - v) > tolerance for v in values[1:]):
            return MismatchDetail("AMOUNT_MISMATCH", "Tax amount mismatch between invoice/returns/payment", "Value inconsistency", 25)
        return None

    def _risk_score(self, invoice: Node, mismatches: List[MismatchDetail]) -> float:
        exposure = min(35.0, float(invoice.attrs.get("tax_amount", 0.0)) / 10000.0)
        severity = float(sum(m.severity_weight for m in mismatches))
        return min(100.0, round(exposure + severity, 2))

    def _risk_level_from_score(self, score: float) -> RiskLevel:
        if score >= 80:
            return RiskLevel.CRITICAL
        if score >= 55:
            return RiskLevel.HIGH
        if score >= 30:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _risk_rank(self, level: RiskLevel) -> int:
        return {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4}[level]

    def _mismatch_ratio(self, rows: List[ReconciliationResult], code: str) -> float:
        if not rows:
            return 0.0
        return sum(1 for r in rows if any(m.code == code for m in r.mismatches)) / len(rows)

    def _graph_pressure_score(self) -> float:
        invoices = max(1, len(self.graph.invoice_ids()))
        broken = invoices - self.graph.relation_count("DECLARED_IN_GSTR1")
        return min(1.0, broken / invoices)

    def _require_node(self, node_id: str, expected: EntityType) -> Node:
        node = self.graph.node(node_id)
        if node is None:
            raise KeyError(f"Unknown node {node_id}")
        if node.entity_type != expected:
            raise ValueError(f"Node {node_id} is {node.entity_type.value}, expected {expected.value}")
        return node


def build_demo_graph() -> GSTKnowledgeGraph:
    g = GSTKnowledgeGraph()
    ing = GSTDataIngestion(g)

    ing.ingest_taxpayer("27ABCDE1234F1Z5", "Alpha Components LLP")
    ing.ingest_taxpayer("29PQRSX5678L1Z2", "Beta Metals Pvt Ltd")

    ing.ingest_invoices(
        [
            {"invoice_id": "INV-1001", "supplier_gstin": "27ABCDE1234F1Z5", "tax_amount": 18000.0},
            {"invoice_id": "INV-2001", "supplier_gstin": "29PQRSX5678L1Z2", "tax_amount": 250000.0},
            {"invoice_id": "INV-3001", "supplier_gstin": "29PQRSX5678L1Z2", "tax_amount": 120000.0},
        ]
    )

    g.add_node(Node("GSTR3B::2024-04::A", EntityType.RETURN_GSTR3B, {"tax_amount": 18000.0}))
    g.add_node(Node("PMT::2024-04::A", EntityType.TAX_PAYMENT, {"tax_amount": 18000.0}))

    ing.ingest_gstr1([{"period": "2024-04", "invoice_id": "INV-1001", "tax_amount": 18000.0}])
    ing.ingest_gstr2b([
        {"period": "2024-04", "invoice_id": "INV-1001", "tax_amount": 18000.0},
        {"period": "2024-04", "invoice_id": "INV-2001", "tax_amount": 240000.0},
        {"period": "2024-04", "invoice_id": "INV-3001", "tax_amount": 120000.0},
    ])
    ing.ingest_purchase_register([{"period": "2024-04", "invoice_id": "INV-1001", "tax_amount": 18000.0}])
    ing.ingest_einvoice([{"invoice_id": "INV-1001", "irn": "IRN-1001", "irn_valid": True}])

    g.add_edge(Edge("GSTR1::2024-04::INV-1001", "SUMMARIZED_IN_GSTR3B", "GSTR3B::2024-04::A"))
    g.add_edge(Edge("GSTR3B::2024-04::A", "SETTLED_BY_PAYMENT", "PMT::2024-04::A"))
    return g

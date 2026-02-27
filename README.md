# GST Knowledge Graph Reconciliation Platform

A graph-native GST reconciliation platform designed for FinTech-grade compliance analytics.

## Stack Alignment

- **Graph Layer:** NetworkX abstraction (portable to Neo4j / Amazon Neptune / ArangoDB)
- **Backend APIs:** FastAPI-style REST endpoints (`api.py`)
- **Dashboard:** React + Vite (`dashboard/`)
- **Domain:** GST reconciliation, ITC leakage detection, vendor compliance intelligence

## Core Capabilities

1. **Knowledge Graph schema + data model**
   - Entities: Taxpayer, GSTIN, Invoice, IRN, Purchase Register, GSTR-1, GSTR-2B, GSTR-3B, Tax Payment
   - Directed relationships for filing, reflection, booking, and settlement continuity

2. **Reconciliation engine with mismatch classification**
   - Multi-hop chain validation: `INVOICE -> GSTR1 -> GSTR3B -> PAYMENT`
   - Root-cause coded mismatches: filing gaps, chain breaks, IRN gaps, amount mismatch/data gap

3. **Interactive ITC risk dashboard**
   - Filter by supplier GSTIN, minimum risk, mismatch-only
   - Shows invoice-level risk rows, aggregate ITC exposure, and top vendor risk profiles

4. **Explainable audit trail generator**
   - Human-readable invoice narratives and traversal trails for audit support

5. **Predictive vendor compliance model**
   - Feature-based risk score using mismatch rate, pattern ratios, and graph pressure indicators

## REST Endpoints

- `GET /health`
- `GET /api/reconciliation/invoices`
- `GET /api/reconciliation/invoices/{invoice_id}`
- `GET /api/audit/{invoice_id}`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/view?min_risk=HIGH&only_mismatch=true`
- `GET /api/vendors/risk`

## Run Tests

```bash
python -m pytest -q
```

## Run API

```bash
uvicorn api:app --reload
```

## Run Dashboard

```bash
cd dashboard
npm install
npm run dev
```

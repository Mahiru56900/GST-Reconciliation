import React, { useEffect, useState } from 'react'

const API = 'http://localhost:8000/api'

export default function App() {
  const [minRisk, setMinRisk] = useState('ALL')
  const [onlyMismatch, setOnlyMismatch] = useState(false)
  const [supplier, setSupplier] = useState('')
  const [data, setData] = useState(null)

  const load = () => {
    const params = new URLSearchParams()
    if (minRisk !== 'ALL') params.set('min_risk', minRisk)
    if (supplier.trim()) params.set('supplier_gstin', supplier.trim())
    if (onlyMismatch) params.set('only_mismatch', 'true')
    fetch(`${API}/dashboard/view?${params.toString()}`)
      .then(r => r.json())
      .then(setData)
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div style={{ fontFamily: 'Arial', padding: 20 }}>
      <h2>GST ITC Risk & Vendor Compliance Dashboard</h2>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select value={minRisk} onChange={e => setMinRisk(e.target.value)}>
          <option>ALL</option>
          <option>MEDIUM</option>
          <option>HIGH</option>
          <option>CRITICAL</option>
        </select>
        <input value={supplier} onChange={e => setSupplier(e.target.value)} placeholder="Supplier GSTIN" />
        <label>
          <input type="checkbox" checked={onlyMismatch} onChange={e => setOnlyMismatch(e.target.checked)} />
          Only mismatches
        </label>
        <button onClick={load}>Apply</button>
      </div>

      {data && (
        <>
          <pre>{JSON.stringify(data.summary, null, 2)}</pre>

          <h3>Invoices</h3>
          <table border="1" cellPadding="6">
            <thead>
              <tr><th>Invoice</th><th>Status</th><th>Risk</th><th>Score</th><th>Mismatches</th></tr>
            </thead>
            <tbody>
              {data.rows.map(row => (
                <tr key={row.invoice_id}>
                  <td>{row.invoice_id}</td>
                  <td>{row.status}</td>
                  <td>{row.risk_level}</td>
                  <td>{row.risk_score}</td>
                  <td>{row.mismatches.map(m => m.code).join(', ') || 'None'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Top Vendors</h3>
          <ul>
            {data.top_vendors.map(v => (
              <li key={v.supplier_gstin}>
                {v.supplier_gstin} - {v.predicted_risk} ({v.predictive_score})
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

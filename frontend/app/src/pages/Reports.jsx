import { useState } from 'react'
import { useRevenueReport } from '../api/queries'
import {
  Alert, Badge, Card, Empty, Field, Input, Money, PageTitle, QueryState, Row, Rows,
} from '../components/ui'

function Figure({ label, value, hint, tone }) {
  return (
    <div className="px-4 py-3">
      <span className="block text-xs text-muted">{label}</span>
      <Money value={value} className={`text-lg font-semibold ${tone ?? 'text-ink'}`} />
      {hint && <span className="mt-0.5 block text-xs text-muted">{hint}</span>}
    </div>
  )
}

/** A split, with each row's share shown as a bar so the shape is readable at a glance. */
function Split({ title, rows, empty, nameKey = 'label' }) {
  const largest = rows.reduce((top, row) => Math.max(top, Number(row.total)), 0)

  return (
    <Card title={title}>
      {rows.length ? (
        <Rows>
          {rows.map((row) => (
            <Row key={row.key ?? row.name}>
              <div className="min-w-0 flex-1">
                <span className="text-sm text-ink">
                  {row[nameKey] ?? row.name}
                  {row.is_loss && <Badge tone="warn"> loss</Badge>}
                </span>
                <span
                  aria-hidden="true"
                  className="mt-1 block h-1 rounded-full bg-brand-600/70"
                  style={{ width: largest ? `${(Number(row.total) / largest) * 100}%` : 0 }}
                />
              </div>
              <Money value={row.total} className="text-sm" />
            </Row>
          ))}
        </Rows>
      ) : (
        <Empty>{empty}</Empty>
      )}
    </Card>
  )
}

export default function Reports() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const query = useRevenueReport(from, to)
  const report = query.data

  return (
    <>
      <PageTitle meta={report && `${report.from} to ${report.to}`}>Revenue and profit</PageTitle>

      {report?.invalid_range && (
        <Alert tone="warn">That range could not be read in full — showing what it could.</Alert>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <Field label="From">
          <Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label="To">
          <Input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </Field>
      </div>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title={`${report?.days} ${report?.days === 1 ? 'day' : 'days'}`}>
            <div className="grid divide-y divide-line sm:grid-cols-4 sm:divide-x sm:divide-y-0">
              <Figure
                label="Collected"
                value={report?.revenue}
                hint={`${report?.receipts} ${report?.receipts === 1 ? 'receipt' : 'receipts'}`}
              />
              <Figure label="Stock used" value={report?.cost} hint="At what it was bought for" />
              <Figure
                label="Profit"
                value={report?.profit}
                tone={Number(report?.profit) < 0 ? 'text-danger' : 'text-good'}
                hint="Revenue less the stock that left"
              />
              <Figure
                label="Written off"
                value={report?.losses}
                tone="text-warn"
                hint="Wastage, expiry and corrections"
              />
            </div>

            {/* Said plainly rather than left for someone to discover. */}
            <p className="border-t border-line px-4 py-2 text-xs text-muted">
              Only the pharmacy and the procedure room have a recorded cost. Consultation and
              laboratory revenue carries no cost of sale here, so profit is overstated by whatever
              reagents and time cost.
            </p>
          </Card>

          <Card title="Day by day">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="px-4 py-2 font-medium">Day</th>
                    <th className="px-4 py-2 text-right font-medium">Collected</th>
                    <th className="px-4 py-2 text-right font-medium">Stock used</th>
                    <th className="px-4 py-2 text-right font-medium">Profit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {(report?.daily ?? []).map((row) => (
                    <tr key={row.day}>
                      <td className="px-4 py-2 text-ink">
                        {new Date(`${row.day}T00:00:00`).toLocaleDateString([], {
                          weekday: 'short',
                          day: '2-digit',
                          month: 'short',
                        })}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Money value={row.revenue} />
                      </td>
                      <td className="px-4 py-2 text-right text-muted">
                        <Money value={row.cost} />
                      </td>
                      <td className="px-4 py-2 text-right font-medium">
                        <Money
                          value={row.profit}
                          className={Number(row.profit) < 0 ? 'text-danger' : undefined}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            <Split
              title="By department"
              rows={report?.by_department ?? []}
              empty="Nothing was taken in this period."
            />
            <Split
              title="By payment method"
              rows={(report?.by_method ?? []).filter((row) => Number(row.total) > 0)}
              empty="Nothing was taken in this period."
            />
            <Split
              title="By cashier"
              rows={report?.by_cashier ?? []}
              empty="Nobody took a payment in this period."
              nameKey="name"
            />
            <Split
              title="Where the stock went"
              rows={report?.cost_by_reason ?? []}
              empty="No stock left the shelf in this period."
            />
          </div>
        </div>
      </QueryState>
    </>
  )
}

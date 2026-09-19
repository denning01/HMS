import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCollections } from '../api/queries'
import { Alert, Card, Empty, Money, PageTitle, QueryState, Row, Rows, Input } from '../components/ui'

function Stat({ label, value, tone }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
      <span className="block text-xs text-muted">{label}</span>
      <Money value={value} className={`text-2xl font-semibold ${tone ?? 'text-ink'}`} />
    </div>
  )
}

function Split({ title, rows, nameKey = 'label', showZero = false }) {
  const visible = showZero ? rows : rows.filter((row) => Number(row.total) > 0)
  return (
    <Card title={title}>
      {visible.length ? (
        <Rows>
          {visible.map((row) => (
            <Row key={row[nameKey]}>
              <span className={`text-sm ${Number(row.total) ? 'text-ink' : 'text-muted'}`}>
                {row[nameKey]}
              </span>
              <Money
                value={row.total}
                className={`text-sm ${Number(row.total) ? 'text-ink' : 'text-muted'}`}
              />
            </Row>
          ))}
        </Rows>
      ) : (
        <Empty>Nothing collected.</Empty>
      )}
    </Card>
  )
}

export default function Collections() {
  const [day, setDay] = useState('')
  const query = useCollections(day)
  const data = query.data

  return (
    <>
      <PageTitle
        meta={
          <Input
            type="date"
            value={data?.day ?? ''}
            onChange={(event) => setDay(event.target.value)}
            className="w-auto"
            aria-label="Day"
          />
        }
      >
        Collections {data?.is_today && <span className="text-muted">today</span>}
      </PageTitle>

      <QueryState query={query}>
        {data?.invalid_day && <Alert tone="warn">That is not a date — showing today instead.</Alert>}

        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <Stat label={`Collected ${data?.day ?? ''}`} value={data?.total} />
          <Stat label="Outstanding on all open bills" value={data?.outstanding} tone="text-muted" />
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {/* Methods with nothing taken stay listed: a reconciliation that hides
              an empty till is one a cashier cannot check. */}
          <Split title="By method" rows={data?.by_method ?? []} showZero />
          <Split title="By department" rows={data?.by_department ?? []} />
          <Split title="By cashier" rows={data?.by_cashier ?? []} nameKey="name" />
        </div>

        <Card title="Receipts" className="mt-4">
          {data?.payments?.length ? (
            <Rows>
              {data.payments.map((payment) => (
                <Row key={payment.id}>
                  <div>
                    <Link className="text-sm text-brand-700" to={`/billing/receipts/${payment.id}`}>
                      {payment.receipt_number}
                    </Link>
                    <span className="mt-0.5 block text-xs text-muted">
                      {new Date(payment.received_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}{' '}
                      · {payment.method_display}
                      {payment.reference && ` · ${payment.reference}`} · {payment.received_by_name}
                    </span>
                  </div>
                  <Money value={payment.amount} className="text-sm" />
                </Row>
              ))}
            </Rows>
          ) : (
            <Empty>No receipts issued on this day.</Empty>
          )}
        </Card>
      </QueryState>
    </>
  )
}

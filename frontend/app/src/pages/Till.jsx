import { useState } from 'react'
import { useTill } from '../api/queries'
import { Badge, Button, Card, Empty, Input, Money, PageTitle, QueryState, Row, Rows } from '../components/ui'

export default function Till() {
  const [term, setTerm] = useState('')
  const query = useTill(term)
  const invoices = query.data ?? []

  return (
    <>
      <PageTitle meta={query.data ? `${invoices.length} outstanding` : undefined}>
        Point of sale
      </PageTitle>

      <Input
        type="search"
        value={term}
        onChange={(event) => setTerm(event.target.value)}
        placeholder="Patient name, MRN or bill number"
        autoFocus
        className="mb-4"
        aria-label="Search bills"
      />

      <QueryState query={query}>
        <Card>
          {invoices.length ? (
            <Rows>
              {invoices.map((invoice) => (
                <Row key={invoice.id}>
                  <div>
                    <span className="text-sm font-medium text-ink">{invoice.patient_name}</span>
                    {invoice.billing_mode === 'consolidated' && <Badge tone="quiet"> Consolidated</Badge>}
                    <span className="mt-0.5 block text-sm text-muted">
                      {invoice.mrn} · {invoice.number} ·{' '}
                      {new Date(invoice.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Money value={invoice.balance} className="text-sm font-semibold" />
                    <Button as="link" to={`/billing/invoices/${invoice.id}`}>
                      Open bill
                    </Button>
                  </div>
                </Row>
              ))}
            </Rows>
          ) : (
            <Empty>
              {term
                ? `No outstanding bill matches “${term}”.`
                : 'Nothing outstanding — every open visit is paid up.'}
            </Empty>
          )}
        </Card>
      </QueryState>
    </>
  )
}

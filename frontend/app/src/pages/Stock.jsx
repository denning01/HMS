import { useStock } from '../api/queries'
import { Badge, Button, Card, Empty, PageTitle, QueryState, Row, Rows } from '../components/ui'

function expiryTone(days) {
  if (days < 0) return 'danger'
  if (days <= 30) return 'danger'
  return 'warn'
}

function expiryLabel(batch) {
  if (batch.is_expired) return 'expired'
  return `${batch.days_to_expiry} days left`
}

export default function Stock() {
  const query = useStock()
  const items = query.data?.items ?? []
  const low = query.data?.low_stock ?? []
  const expiring = query.data?.expiring ?? []

  return (
    <>
      <PageTitle meta={query.data ? `${items.length} items` : undefined}>Stock</PageTitle>

      <QueryState query={query}>
        <div className="grid gap-4">
          {/* The two things worth interrupting a pharmacist for, first. */}
          <Card title="To reorder">
            {low.length ? (
              <Rows>
                {low.map((item) => (
                  <Row key={item.id}>
                    <div>
                      <span className="text-sm text-ink">
                        {item.name} {item.strength}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">
                        reorder level {item.reorder_level} {item.unit}s
                      </span>
                    </div>
                    <Badge tone={item.quantity === 0 ? 'danger' : 'warn'}>
                      {item.quantity} {item.unit}
                      {item.quantity === 1 ? '' : 's'} left
                    </Badge>
                  </Row>
                ))}
              </Rows>
            ) : (
              <Empty>Nothing is below its reorder level.</Empty>
            )}
          </Card>

          <Card title="Expiring or expired">
            {expiring.length ? (
              <Rows>
                {expiring.map((batch) => (
                  <Row key={batch.id}>
                    <div>
                      <span className="text-sm text-ink">{batch.item_name}</span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {batch.batch_number || 'no batch number'} · {batch.quantity_remaining}{' '}
                        {batch.unit}s · expires {batch.expires_on}
                      </span>
                    </div>
                    <Badge tone={expiryTone(batch.days_to_expiry)}>{expiryLabel(batch)}</Badge>
                  </Row>
                ))}
              </Rows>
            ) : (
              <Empty>Nothing expires in the next three months.</Empty>
            )}
          </Card>

          <Card title="On the shelf">
            <Rows>
              {items.map((item) => (
                <Row key={item.id}>
                  <div>
                    <span className="text-sm text-ink">
                      {item.name} {item.strength}
                    </span>
                    {item.is_low && <Badge tone="warn"> Low</Badge>}
                    <span className="mt-0.5 block text-xs text-muted">
                      {item.form_display}
                      {item.service_code ? ` · ${item.service_code}` : ' · not sold separately'}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-ink tabular">
                      {item.quantity} {item.unit}
                      {item.quantity === 1 ? '' : 's'}
                    </span>
                    <Button variant="secondary" as="link" to={`/pharmacy/stock/${item.id}`}>
                      Open
                    </Button>
                  </div>
                </Row>
              ))}
            </Rows>
          </Card>
        </div>
      </QueryState>
    </>
  )
}

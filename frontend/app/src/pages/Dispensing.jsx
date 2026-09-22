import { useDispensingQueue } from '../api/queries'
import { Badge, Button, Card, Empty, Money, PageTitle, QueryState, Row, Rows } from '../components/ui'

function waited(minutes) {
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

function PrescriptionRow({ order, action }) {
  const stock = order.stock

  return (
    <Row>
      <div className="min-w-0">
        <span className="text-sm font-medium text-ink">
          {order.name} <span className="text-muted">×{order.quantity}</span>
        </span>
        {order.is_urgent && <Badge tone="danger"> Urgent</Badge>}
        {stock && !stock.is_enough && <Badge tone="danger"> Short: {stock.available} left</Badge>}

        <span className="mt-0.5 block text-sm text-muted">
          {order.patient_name} · {order.mrn} · waiting {waited(order.waiting_minutes)}
        </span>
        {order.prescription?.directions && (
          <span className="mt-0.5 block text-xs text-ink">{order.prescription.directions}</span>
        )}
        {!stock && (
          <span className="mt-0.5 block text-xs text-warn">
            Not on the stock list — add it before dispensing.
          </span>
        )}
      </div>
      {action}
    </Row>
  )
}

export default function Dispensing() {
  const query = useDispensingQueue()
  const ready = query.data?.ready ?? []
  const held = query.data?.awaiting_payment ?? []

  return (
    <>
      <PageTitle meta={query.data ? `${ready.length} to dispense` : undefined}>
        Dispensing queue
      </PageTitle>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title="Ready to dispense">
            {ready.length ? (
              <Rows>
                {ready.map((order) => (
                  <PrescriptionRow
                    key={order.id}
                    order={order}
                    action={
                      <Button as="link" to={`/pharmacy/orders/${order.id}`}>
                        Open
                      </Button>
                    }
                  />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing is waiting to be dispensed.</Empty>
            )}
          </Card>

          <Card title="Waiting on payment">
            {held.length ? (
              <Rows>
                {held.map((order) => (
                  <PrescriptionRow
                    key={order.id}
                    order={order}
                    action={
                      <div className="text-right">
                        <Money value={order.line_total} className="block text-sm" />
                        <span className="text-xs text-warn">at the till</span>
                      </div>
                    }
                  />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing is held up at the till.</Empty>
            )}
          </Card>
        </div>
      </QueryState>
    </>
  )
}

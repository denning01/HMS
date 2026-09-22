import { useLabWorklist } from '../api/queries'
import { Badge, Button, Card, Empty, Money, PageTitle, QueryState, Row, Rows } from '../components/ui'

const STAGE_TONES = {
  'awaiting specimen': 'neutral',
  'specimen collected': 'warn',
  'awaiting release': 'warn',
  released: 'good',
}

function waited(minutes) {
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

function OrderRow({ order, action }) {
  return (
    <Row>
      <div className="min-w-0">
        <span className="text-sm font-medium text-ink">{order.name}</span>
        {order.is_urgent && <Badge tone="danger"> Urgent</Badge>}
        {order.result && (
          <Badge tone={STAGE_TONES[order.result.stage]}> {order.result.stage}</Badge>
        )}
        <span className="mt-0.5 block text-sm text-muted">
          {order.patient_name} · {order.mrn} · {order.sex} {order.age} yrs · waiting{' '}
          {waited(order.waiting_minutes)}
        </span>
        <span className="mt-0.5 block text-xs text-muted">
          {order.specimen}
          {order.clinical_details && ` · ${order.clinical_details}`}
        </span>
      </div>
      {action}
    </Row>
  )
}

export default function LabWorklist() {
  const query = useLabWorklist()
  const ready = query.data?.ready ?? []
  const held = query.data?.awaiting_payment ?? []

  return (
    <>
      <PageTitle meta={query.data ? `${ready.length} to run` : undefined}>Lab worklist</PageTitle>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title="Ready to run">
            {ready.length ? (
              <Rows>
                {ready.map((order) => (
                  <OrderRow
                    key={order.id}
                    order={order}
                    action={
                      <Button as="link" to={`/lab/orders/${order.id}`}>
                        Open
                      </Button>
                    }
                  />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing is waiting to be run.</Empty>
            )}
          </Card>

          {/* Shown rather than hidden: a technician with no sight of these has no
              answer for the patient asking why their test has not been done. */}
          <Card title="Waiting on payment">
            {held.length ? (
              <Rows>
                {held.map((order) => (
                  <OrderRow
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

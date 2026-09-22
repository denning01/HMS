import { useNavigate, useParams } from 'react-router-dom'
import { useDispense, usePrescription } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Money, PageTitle, QueryState, Row, Rows,
} from '../components/ui'

function Detail({ label, children }) {
  return (
    <div>
      <span className="block text-xs text-muted">{label}</span>
      <span className="text-sm text-ink">{children || '—'}</span>
    </div>
  )
}

export default function DispenseOrder() {
  const { orderId } = useParams()
  const navigate = useNavigate()

  const query = usePrescription(orderId)
  const dispense = useDispense(orderId)

  const order = query.data
  const prescription = order?.prescription
  const stock = order?.stock
  const dispensed = Boolean(prescription?.is_dispensed)

  async function give() {
    const done = await dispense.mutateAsync().catch(() => null)
    if (done) navigate('/pharmacy')
  }

  return (
    <QueryState query={query}>
      <PageTitle meta={order && `${order.mrn} · ${order.sex} ${order.age} yrs`}>
        {order?.name} — {order?.patient_name}
      </PageTitle>

      <Alert>{dispense.error?.message}</Alert>

      <div className="grid gap-4">
        <Card
          title="Prescription"
          actions={<Badge tone={dispensed ? 'good' : 'neutral'}>{dispensed ? 'Dispensed' : 'To dispense'}</Badge>}
        >
          <div className="grid gap-3 p-4 sm:grid-cols-4">
            <Detail label="Quantity">
              {order?.quantity} {stock?.unit ?? 'unit'}
              {order?.quantity === 1 ? '' : 's'}
            </Detail>
            <Detail label="Dose">{prescription?.dosage}</Detail>
            <Detail label="How often">{prescription?.frequency}</Detail>
            <Detail label="For how long">{prescription?.duration}</Detail>
          </div>

          {prescription?.instructions && (
            <p className="border-t border-line px-4 py-3 text-sm text-ink">
              <span className="mb-0.5 block text-xs text-muted">Instructions</span>
              {prescription.instructions}
            </p>
          )}

          <footer className="flex items-center justify-between border-t border-line px-4 py-3">
            <span className="text-sm text-muted">
              Prescribed by {order?.ordered_by_name}
              {dispensed &&
                ` · dispensed by ${prescription.dispensed_by_name} at ${new Date(
                  prescription.dispensed_at,
                ).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
            </span>
            <Money value={order?.line_total} className="text-sm" />
          </footer>
        </Card>

        <Card title="On the shelf">
          {stock ? (
            <Rows>
              <Row>
                <span className="text-sm text-muted">{stock.name}, in date</span>
                <span className="text-sm text-ink tabular">
                  {stock.available} {stock.unit}
                  {stock.available === 1 ? '' : 's'}
                </span>
              </Row>
              <Row>
                <span className="text-sm text-muted">Enough for this prescription</span>
                <Badge tone={stock.is_enough ? 'good' : 'danger'}>
                  {stock.is_enough ? 'Yes' : 'No — short'}
                </Badge>
              </Row>
            </Rows>
          ) : (
            <Empty>This drug is on the price list but not on the stock list.</Empty>
          )}

          <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">
            <Button variant="secondary" as="link" to="/pharmacy">
              Back to queue
            </Button>
            {!dispensed && (
              <Button onClick={give} disabled={!stock?.is_enough || dispense.isPending}>
                {dispense.isPending ? 'Dispensing…' : 'Dispense'}
              </Button>
            )}
          </footer>
        </Card>
      </div>
    </QueryState>
  )
}

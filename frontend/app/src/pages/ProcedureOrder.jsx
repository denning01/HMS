import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePerformProcedure, useProcedureOrder } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, Money, PageTitle, QueryState,
  Row, Rows, Textarea,
} from '../components/ui'

export default function ProcedureOrder() {
  const { orderId } = useParams()
  const navigate = useNavigate()

  const query = useProcedureOrder(orderId)
  const performProcedure = usePerformProcedure(orderId)

  const order = query.data?.order
  const record = order?.record
  const consumables = query.data?.consumables ?? []
  const done = Boolean(record?.is_performed)

  const [notes, setNotes] = useState('')
  // Keyed by stock item id; only the ones actually reached for are sent.
  const [used, setUsed] = useState({})

  async function submit(event) {
    event.preventDefault()
    const payload = {
      notes,
      consumables: Object.entries(used)
        .filter(([, quantity]) => Number(quantity) > 0)
        .map(([item, quantity]) => ({ item: Number(item), quantity: Number(quantity) })),
    }
    const result = await performProcedure.mutateAsync(payload).catch(() => null)
    if (result) navigate('/procedures')
  }

  return (
    <QueryState query={query}>
      <PageTitle meta={order && `${order.mrn} · ${order.sex} ${order.age} yrs`}>
        {order?.name} — {order?.patient_name}
      </PageTitle>

      <Alert>{performProcedure.error?.message}</Alert>

      <form onSubmit={submit} className="grid gap-4">
        <Card
          title="The request"
          actions={<Badge tone={done ? 'good' : 'neutral'}>{done ? 'Done' : 'To do'}</Badge>}
        >
          <div className="p-4">
            <span className="block text-xs text-muted">Ordered by</span>
            <span className="text-sm text-ink">{order?.ordered_by_name}</span>
            {order?.clinical_details && (
              <p className="mt-3 text-sm text-ink">
                <span className="mb-0.5 block text-xs text-muted">Clinical details</span>
                {order.clinical_details}
              </p>
            )}
          </div>
        </Card>

        {done ? (
          <Card title="What was done">
            <div className="p-4">
              <p className="text-sm text-ink">{record.notes || 'No notes were written.'}</p>
              <span className="mt-2 block text-xs text-muted">
                {record.performed_by_name} ·{' '}
                {new Date(record.performed_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>

            {record.consumables.length > 0 && (
              <>
                <Rows>
                  {record.consumables.map((movement) => (
                    <Row key={movement.id}>
                      <span className="text-sm text-ink">
                        {Math.abs(movement.quantity)} × {movement.reason_display.toLowerCase()}
                        {movement.batch_number && ` · batch ${movement.batch_number}`}
                      </span>
                      <Money value={movement.cost_total} className="text-sm text-muted" />
                    </Row>
                  ))}
                </Rows>
                <footer className="flex items-center justify-between border-t border-line px-4 py-3">
                  <span className="text-sm text-muted">Consumables used</span>
                  <Money value={record.consumable_cost} className="text-sm font-semibold" />
                </footer>
              </>
            )}
          </Card>
        ) : (
          <Card title="Record the procedure">
            <div className="p-4">
              <Field label="Notes" hint="What was done, and how the patient tolerated it">
                <Textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
              </Field>

              <p className="mt-4 mb-2 text-sm font-medium text-ink">Consumables used</p>
              {consumables.length ? (
                <div className="grid gap-3 sm:grid-cols-3">
                  {consumables.map((item) => (
                    <Field
                      key={item.id}
                      label={`${item.name} ${item.strength}`.trim()}
                      hint={`${item.in_date_quantity} ${item.unit}s in date`}
                    >
                      <Input
                        type="number"
                        min="0"
                        max={item.in_date_quantity}
                        value={used[item.id] ?? ''}
                        onChange={(event) =>
                          setUsed({ ...used, [item.id]: event.target.value })
                        }
                        placeholder="0"
                      />
                    </Field>
                  ))}
                </div>
              ) : (
                <Empty>Nothing in date on the shelf to draw on.</Empty>
              )}
            </div>

            <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">
              <Button variant="secondary" as="link" to="/procedures">
                Back to the room
              </Button>
              <Button type="submit" disabled={performProcedure.isPending}>
                {performProcedure.isPending ? 'Recording…' : 'Record as done'}
              </Button>
            </footer>
          </Card>
        )}
      </form>
    </QueryState>
  )
}

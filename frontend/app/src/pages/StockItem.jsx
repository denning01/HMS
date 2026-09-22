import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useReceiveStock, useStockItem, useWriteOff } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, Money, PageTitle, QueryState,
  Row, Rows, Select,
} from '../components/ui'

const WRITE_OFF_REASONS = [
  { value: 'wastage', label: 'Wastage or breakage' },
  { value: 'expired', label: 'Written off, expired' },
  { value: 'correction', label: 'Stock count correction' },
]

const BLANK_DELIVERY = {
  quantity: '',
  unit_cost: '',
  expires_on: '',
  batch_number: '',
  supplier: '',
}

function ReceiveForm({ itemId, unit }) {
  const receive = useReceiveStock(itemId)
  const [values, setValues] = useState(BLANK_DELIVERY)

  const set = (name) => (event) => setValues({ ...values, [name]: event.target.value })
  const fieldError = (name) => receive.error?.fields?.[name]?.[0]

  async function submit(event) {
    event.preventDefault()
    const batch = await receive.mutateAsync(values).catch(() => null)
    if (batch) setValues(BLANK_DELIVERY)
  }

  return (
    <form onSubmit={submit}>
      <Card title="Receive a delivery">
        <div className="p-4">
          {receive.error?.message && !Object.keys(receive.error.fields).length && (
            <Alert>{receive.error.message}</Alert>
          )}

          <div className="grid gap-3 sm:grid-cols-5">
            <Field label={`Quantity (${unit}s)`} error={fieldError('quantity')}>
              <Input type="number" min="1" value={values.quantity} onChange={set('quantity')} required />
            </Field>
            <Field label="Unit cost" hint="What was paid" error={fieldError('unit_cost')}>
              <Input type="number" step="0.01" min="0" value={values.unit_cost} onChange={set('unit_cost')} required />
            </Field>
            <Field label="Expires on" error={fieldError('expires_on')}>
              <Input type="date" value={values.expires_on} onChange={set('expires_on')} required />
            </Field>
            <Field label="Batch number">
              <Input value={values.batch_number} onChange={set('batch_number')} />
            </Field>
            <Field label="Supplier">
              <Input value={values.supplier} onChange={set('supplier')} />
            </Field>
          </div>
        </div>

        <footer className="flex justify-end border-t border-line px-4 py-3">
          <Button type="submit" disabled={receive.isPending}>
            {receive.isPending ? 'Receiving…' : 'Receive'}
          </Button>
        </footer>
      </Card>
    </form>
  )
}

function WriteOffForm({ batch, onDone }) {
  const writeOff = useWriteOff()
  const [quantity, setQuantity] = useState('')
  const [reason, setReason] = useState('wastage')
  const [note, setNote] = useState('')

  async function submit(event) {
    event.preventDefault()
    const done = await writeOff
      .mutateAsync({ batchId: batch.id, quantity: Number(quantity), reason, note })
      .catch(() => null)
    if (done) onDone()
  }

  return (
    <form onSubmit={submit} className="border-t border-line bg-canvas px-4 py-3">
      <Alert>{writeOff.error?.message}</Alert>
      <div className="grid items-end gap-3 sm:grid-cols-4">
        <Field label="Quantity">
          <Input
            type="number"
            min="1"
            max={batch.quantity_remaining}
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            required
          />
        </Field>
        <Field label="Reason">
          <Select value={reason} onChange={(event) => setReason(event.target.value)}>
            {WRITE_OFF_REASONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Note" className="sm:col-span-2">
          <Input value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={!quantity || writeOff.isPending}>
          {writeOff.isPending ? 'Writing off…' : 'Write off'}
        </Button>
      </div>
    </form>
  )
}

export default function StockItem() {
  const { itemId } = useParams()
  const query = useStockItem(itemId)
  const [writingOff, setWritingOff] = useState(null)

  const item = query.data?.item
  const batches = query.data?.batches ?? []
  const movements = query.data?.movements ?? []

  return (
    <QueryState query={query}>
      <PageTitle
        meta={item && `${item.quantity} ${item.unit}${item.quantity === 1 ? '' : 's'} on the shelf`}
      >
        {item?.name} {item?.strength}
      </PageTitle>

      {item?.is_low && (
        <Alert tone="warn">
          At or below the reorder level of {item.reorder_level} {item.unit}s.
        </Alert>
      )}

      <div className="grid gap-4">
        <ReceiveForm itemId={itemId} unit={item?.unit ?? 'unit'} />

        <Card title="Batches">
          {batches.length ? (
            <ul className="divide-y divide-line">
              {batches.map((batch) => (
                <li key={batch.id}>
                  <div className="flex items-center justify-between gap-4 px-4 py-3">
                    <div>
                      <span className="text-sm text-ink">
                        {batch.batch_number || 'No batch number'}
                      </span>
                      {batch.is_expired && <Badge tone="danger"> Expired</Badge>}
                      <span className="mt-0.5 block text-xs text-muted">
                        {batch.quantity_remaining} of {batch.quantity_received} left · expires{' '}
                        {batch.expires_on}
                        {batch.supplier && ` · ${batch.supplier}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Money value={batch.unit_cost} className="text-sm" />
                      {batch.quantity_remaining > 0 && (
                        <Button
                          variant="quiet"
                          onClick={() => setWritingOff(writingOff === batch.id ? null : batch.id)}
                        >
                          Write off
                        </Button>
                      )}
                    </div>
                  </div>

                  {writingOff === batch.id && (
                    <WriteOffForm batch={batch} onDone={() => setWritingOff(null)} />
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Nothing has been received for this item yet.</Empty>
          )}
        </Card>

        <Card title="Movements">
          {movements.length ? (
            <Rows>
              {movements.map((movement) => (
                <Row key={movement.id}>
                  <div>
                    <span className="text-sm text-ink">
                      {movement.quantity > 0 ? '+' : ''}
                      {movement.quantity} · {movement.reason_display}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted">
                      {new Date(movement.recorded_at).toLocaleString([], {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                      {movement.recorded_by_name && ` · ${movement.recorded_by_name}`}
                      {movement.patient_mrn && ` · ${movement.patient_mrn}`}
                      {movement.note && ` · ${movement.note}`}
                    </span>
                  </div>
                  <Money value={movement.cost_total} className="text-sm text-muted" />
                </Row>
              ))}
            </Rows>
          ) : (
            <Empty>No movements yet.</Empty>
          )}
        </Card>
      </div>
    </QueryState>
  )
}

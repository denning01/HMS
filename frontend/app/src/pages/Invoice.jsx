import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useInvoice, useTakePayment } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Money, PageTitle, QueryState, Row, Rows, Select, Input,
} from '../components/ui'

const METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'mpesa', label: 'M-Pesa' },
  { value: 'card', label: 'Card' },
  { value: 'bank', label: 'Bank transfer' },
]

const LINE_TONES = { paid: 'good', cancelled: 'quiet', unpaid: 'warn' }

export default function Invoice() {
  const { id } = useParams()
  const navigate = useNavigate()
  const query = useInvoice(id)
  const pay = useTakePayment(id)

  const [selected, setSelected] = useState([])
  const [method, setMethod] = useState('')
  const [reference, setReference] = useState('')

  const invoice = query.data
  const lines = invoice?.lines ?? []

  // The figure on screen is a convenience. The server prices the same lines
  // again when the form is posted, so this can never decide what is charged.
  const selectedTotal = lines
    .filter((line) => selected.includes(line.id))
    .reduce((sum, line) => sum + Number(line.line_total), 0)

  function toggle(lineId) {
    setSelected((current) =>
      current.includes(lineId) ? current.filter((value) => value !== lineId) : [...current, lineId],
    )
  }

  async function submit(event) {
    event.preventDefault()
    const receipt = await pay
      .mutateAsync({ lines: selected, method, reference })
      .catch(() => null)
    if (receipt) navigate(`/billing/receipts/${receipt.id}`)
  }

  return (
    <QueryState query={query}>
      <PageTitle meta={`${invoice?.mrn} · ${invoice?.number}`}>{invoice?.patient_name}</PageTitle>

      <form onSubmit={submit} className="grid gap-4">
        <Card
          title="Charges"
          actions={<Badge tone={invoice?.status_label === 'Paid' ? 'good' : 'warn'}>{invoice?.status_label}</Badge>}
        >
          {lines.length ? (
            <Rows>
              {lines.map((line) => {
                const payable = line.status === 'unpaid' && invoice.can_take_payment
                return (
                  <Row key={line.id} className={line.status === 'cancelled' ? 'opacity-60' : undefined}>
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        className="mt-1 size-4 rounded border-line accent-brand-600 disabled:opacity-0"
                        checked={selected.includes(line.id)}
                        onChange={() => toggle(line.id)}
                        disabled={!payable}
                        aria-label={`Pay for ${line.description}`}
                      />
                      <div>
                        <span
                          className={`text-sm text-ink ${line.status === 'cancelled' ? 'line-through' : ''}`}
                        >
                          {line.description}
                          {line.quantity > 1 && <span className="text-muted"> ×{line.quantity}</span>}
                        </span>
                        <span className="mt-0.5 block text-xs text-muted">
                          {line.department_display}
                          {line.receipt_number && ` · receipt ${line.receipt_number}`}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Money value={line.line_total} className="text-sm" />
                      <Badge tone={LINE_TONES[line.status]}>{line.status_display}</Badge>
                    </div>
                  </Row>
                )
              })}
            </Rows>
          ) : (
            <Empty>No charges on this bill yet.</Empty>
          )}

          <footer className="flex items-center justify-between border-t border-line px-4 py-3">
            <span className="text-sm text-muted">Balance</span>
            <Money value={invoice?.balance} className="text-sm font-semibold" />
          </footer>
        </Card>

        {invoice?.can_take_payment && lines.some((line) => line.status === 'unpaid') && (
          <Card title="Take payment">
            <div className="p-4">
              <Alert>{pay.error?.message}</Alert>

              <div className="grid items-end gap-4 sm:grid-cols-3">
                <Field label="Method">
                  <Select value={method} onChange={(event) => setMethod(event.target.value)} required>
                    <option value="">Choose…</option>
                    {METHODS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Reference" hint="M-Pesa code, if any">
                  <Input value={reference} onChange={(event) => setReference(event.target.value)} />
                </Field>
                <div className="sm:text-right">
                  <span className="block text-xs text-muted">Selected</span>
                  <Money value={selectedTotal} className="text-lg font-semibold" />
                </div>
              </div>
            </div>

            <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">
              <Button variant="secondary" as="link" to="/billing">
                Back to till
              </Button>
              <Button type="submit" disabled={selected.length === 0 || !method || pay.isPending}>
                {pay.isPending ? 'Taking payment…' : 'Take payment'}
              </Button>
            </footer>
          </Card>
        )}

        {invoice?.payments?.length > 0 && (
          <Card title="Receipts">
            <Rows>
              {invoice.payments.map((payment) => (
                <Row key={payment.id}>
                  <div>
                    <Button variant="quiet" as="link" to={`/billing/receipts/${payment.id}`}>
                      {payment.receipt_number}
                    </Button>
                    <span className="mt-0.5 block text-xs text-muted">
                      {payment.method_display}
                      {payment.reference && ` · ${payment.reference}`} ·{' '}
                      {new Date(payment.received_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}{' '}
                      · {payment.received_by_name}
                    </span>
                  </div>
                  <Money value={payment.amount} className="text-sm" />
                </Row>
              ))}
            </Rows>
          </Card>
        )}
      </form>
    </QueryState>
  )
}

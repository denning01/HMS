import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useAdminStockItems,
  useCreateStockItem,
  useServices,
  useUpdateStockItem,
} from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, PageTitle, QueryState, Row, Rows, Select,
} from '../components/ui'

const FORMS = [
  { value: 'tablet', label: 'Tablet' },
  { value: 'capsule', label: 'Capsule' },
  { value: 'syrup', label: 'Syrup' },
  { value: 'injection', label: 'Injection' },
  { value: 'cream', label: 'Cream or ointment' },
  { value: 'drops', label: 'Drops' },
  { value: 'sachet', label: 'Sachet' },
  { value: 'consumable', label: 'Consumable' },
]

const BLANK = {
  name: '',
  generic_name: '',
  form: 'tablet',
  strength: '',
  unit: 'unit',
  reorder_level: '0',
  service: '',
}

function StockRow({ item }) {
  const update = useUpdateStockItem()
  const [level, setLevel] = useState(null)

  async function save() {
    const saved = await update
      .mutateAsync({ id: item.id, reorder_level: Number(level) })
      .catch(() => null)
    if (saved) setLevel(null)
  }

  return (
    <Row>
      <div className="min-w-0">
        <Link to={`/pharmacy/stock/${item.id}`} className="text-sm text-brand-700 hover:underline">
          {item.name} {item.strength}
        </Link>
        {item.is_low && <Badge tone="warn"> Low</Badge>}
        <span className="mt-0.5 block text-xs text-muted">
          {item.form_display} · one {item.unit}
          {item.service_code ? ` · sold as ${item.service_code}` : ' · not sold separately'}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <span className="text-sm text-ink tabular">
          {item.quantity} {item.unit}
          {item.quantity === 1 ? '' : 's'}
        </span>
        {level === null ? (
          <Button variant="quiet" onClick={() => setLevel(String(item.reorder_level))}>
            Reorder at {item.reorder_level}
          </Button>
        ) : (
          <>
            <Input
              type="number"
              min="0"
              value={level}
              onChange={(event) => setLevel(event.target.value)}
              className="w-24"
              aria-label={`Reorder level for ${item.name}`}
            />
            <Button onClick={save} disabled={update.isPending}>
              Save
            </Button>
            <Button variant="quiet" onClick={() => setLevel(null)}>
              Cancel
            </Button>
          </>
        )}
      </div>
    </Row>
  )
}

export default function StockList() {
  const query = useAdminStockItems()
  const create = useCreateStockItem()
  const drugs = useServices('pharmacy')
  const [values, setValues] = useState(BLANK)

  const set = (name) => (event) => setValues({ ...values, [name]: event.target.value })
  const fieldError = (name) => create.error?.fields?.[name]?.[0]

  async function submit(event) {
    event.preventDefault()
    const payload = {
      ...values,
      reorder_level: Number(values.reorder_level),
      service: values.service ? Number(values.service) : null,
    }
    const item = await create.mutateAsync(payload).catch(() => null)
    if (item) setValues(BLANK)
  }

  return (
    <>
      <PageTitle meta={query.data ? `${query.data.length} items` : undefined}>Stock list</PageTitle>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title="What the clinic counts">
            {query.data?.length ? (
              <Rows>
                {query.data.map((item) => (
                  <StockRow key={item.id} item={item} />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing on the stock list yet.</Empty>
            )}
          </Card>

          <form onSubmit={submit}>
            <Card title="Add an item">
              <div className="p-4">
                {create.error?.message && !Object.keys(create.error.fields).length && (
                  <Alert>{create.error.message}</Alert>
                )}

                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Name" error={fieldError('name')}>
                    <Input value={values.name} onChange={set('name')} required />
                  </Field>
                  <Field label="Generic name" hint="Optional">
                    <Input value={values.generic_name} onChange={set('generic_name')} />
                  </Field>
                  <Field label="Form">
                    <Select value={values.form} onChange={set('form')}>
                      {FORMS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Strength" hint="e.g. 500 mg">
                    <Input value={values.strength} onChange={set('strength')} />
                  </Field>
                  <Field label="One unit is" hint="tablet, ml, piece">
                    <Input value={values.unit} onChange={set('unit')} required />
                  </Field>
                  <Field label="Reorder level" error={fieldError('reorder_level')}>
                    <Input
                      type="number"
                      min="0"
                      value={values.reorder_level}
                      onChange={set('reorder_level')}
                    />
                  </Field>
                  <Field
                    label="Sold as"
                    className="sm:col-span-3"
                    hint="Leave blank for a consumable that is never billed on its own"
                    error={fieldError('service')}
                  >
                    <Select value={values.service} onChange={set('service')}>
                      <option value="">Not sold separately</option>
                      {(drugs.data ?? []).map((service) => (
                        <option key={service.id} value={service.id}>
                          {service.code} — {service.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
              </div>

              <footer className="flex justify-end border-t border-line px-4 py-3">
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? 'Adding…' : 'Add'}
                </Button>
              </footer>
            </Card>
          </form>
        </div>
      </QueryState>
    </>
  )
}

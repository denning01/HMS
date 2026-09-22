import { useState } from 'react'
import { useAdminServices, useCreateService, useUpdateService } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, Money, PageTitle, QueryState,
  Row, Rows, Select,
} from '../components/ui'

const DEPARTMENTS = [
  { value: 'consultation', label: 'Consultation' },
  { value: 'laboratory', label: 'Laboratory' },
  { value: 'pharmacy', label: 'Pharmacy' },
  { value: 'procedure', label: 'Procedure / injection room' },
  { value: 'other', label: 'Other' },
]

const BLANK = { code: '', name: '', department: 'laboratory', unit_price: '' }

function PriceRow({ service }) {
  const update = useUpdateService()
  const [price, setPrice] = useState(null)
  const editing = price !== null

  async function save() {
    const saved = await update.mutateAsync({ id: service.id, unit_price: price }).catch(() => null)
    if (saved) setPrice(null)
  }

  return (
    <Row className={service.is_active ? undefined : 'opacity-60'}>
      <div className="min-w-0">
        <span className="text-sm text-ink">{service.name}</span>
        {!service.is_active && <Badge tone="quiet"> Retired</Badge>}
        <span className="mt-0.5 block text-xs text-muted">
          {service.code} · {service.department_display}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {editing ? (
          <>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              className="w-28"
              aria-label={`Price for ${service.name}`}
            />
            <Button onClick={save} disabled={update.isPending}>
              Save
            </Button>
            <Button variant="quiet" onClick={() => setPrice(null)}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Money value={service.unit_price} className="text-sm" />
            <Button variant="quiet" onClick={() => setPrice(service.unit_price)}>
              Change price
            </Button>
            <Button
              variant="quiet"
              onClick={() => update.mutate({ id: service.id, is_active: !service.is_active })}
              disabled={update.isPending}
            >
              {service.is_active ? 'Retire' : 'Restore'}
            </Button>
          </>
        )}
      </div>
    </Row>
  )
}

export default function PriceList() {
  const [department, setDepartment] = useState('')
  const [values, setValues] = useState(BLANK)

  const query = useAdminServices(department)
  const create = useCreateService()

  const set = (name) => (event) => setValues({ ...values, [name]: event.target.value })
  const fieldError = (name) => create.error?.fields?.[name]?.[0]

  async function submit(event) {
    event.preventDefault()
    const service = await create.mutateAsync(values).catch(() => null)
    if (service) setValues(BLANK)
  }

  return (
    <>
      <PageTitle meta={query.data ? `${query.data.length} services` : undefined}>
        Price list
      </PageTitle>

      <Alert tone="warn">
        A price change applies to charges raised from now on. Bills already issued keep the price
        they were raised at, so nothing a patient has been quoted or paid is rewritten.
      </Alert>

      <div className="mb-4">
        <Field label="Department">
          <Select value={department} onChange={(event) => setDepartment(event.target.value)}>
            <option value="">All</option>
            {DEPARTMENTS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title="Services">
            {query.data?.length ? (
              <Rows>
                {query.data.map((service) => (
                  <PriceRow key={service.id} service={service} />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing on the price list for that department.</Empty>
            )}
          </Card>

          <form onSubmit={submit}>
            <Card title="Add a service">
              <div className="p-4">
                {create.error?.message && !Object.keys(create.error.fields).length && (
                  <Alert>{create.error.message}</Alert>
                )}

                <div className="grid gap-3 sm:grid-cols-4">
                  <Field label="Code" hint="Short and stable" error={fieldError('code')}>
                    <Input value={values.code} onChange={set('code')} required />
                  </Field>
                  <Field label="Name" error={fieldError('name')}>
                    <Input value={values.name} onChange={set('name')} required />
                  </Field>
                  <Field label="Department">
                    <Select value={values.department} onChange={set('department')}>
                      {DEPARTMENTS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Price" error={fieldError('unit_price')}>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={values.unit_price}
                      onChange={set('unit_price')}
                      required
                    />
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

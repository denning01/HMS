import { useParams } from 'react-router-dom'
import { useReceipt } from '../api/queries'
import { Button, Money, QueryState } from '../components/ui'

export default function Receipt() {
  const { id } = useParams()
  const query = useReceipt(id)
  const receipt = query.data

  return (
    <QueryState query={query}>
      <div className="no-print mb-4 flex justify-between">
        <Button variant="secondary" as="link" to={`/billing/invoices/${receipt?.invoice.id}`}>
          Back to bill
        </Button>
        <Button onClick={() => window.print()}>Print</Button>
      </div>

      <article className="mx-auto max-w-md rounded-xl border border-line bg-surface p-6 shadow-sm">
        <header className="mb-5 text-center">
          <h1 className="text-base font-semibold text-ink">Hospital Management System</h1>
          <p className="text-xs text-muted">Official receipt</p>
        </header>

        <dl className="mb-5 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
          <dt className="text-muted">Receipt</dt>
          <dd className="text-ink">{receipt?.receipt_number}</dd>

          <dt className="text-muted">Date</dt>
          <dd className="text-ink">{receipt && new Date(receipt.received_at).toLocaleString()}</dd>

          <dt className="text-muted">Patient</dt>
          <dd className="text-ink">
            {receipt?.patient_name}
            <span className="block text-muted">{receipt?.mrn}</span>
          </dd>

          <dt className="text-muted">Bill</dt>
          <dd className="text-ink">{receipt?.invoice.number}</dd>
        </dl>

        <table className="w-full text-sm">
          <tbody>
            {receipt?.lines.map((line) => (
              <tr key={line.id}>
                <td className="py-1 text-ink">
                  {line.description}
                  {line.quantity > 1 && <span className="text-muted"> ×{line.quantity}</span>}
                </td>
                <td className="py-1 text-right tabular text-ink">
                  {Number(line.line_total).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line">
              <th className="pt-2 text-left font-semibold text-ink">
                Paid ({receipt?.method_display})
              </th>
              <th className="pt-2 text-right font-semibold text-ink">
                <Money value={receipt?.amount} />
              </th>
            </tr>
            {Number(receipt?.invoice.balance) > 0 && (
              <tr>
                <td className="pt-1 text-muted">Balance on bill</td>
                <td className="pt-1 text-right text-muted">
                  <Money value={receipt.invoice.balance} />
                </td>
              </tr>
            )}
          </tfoot>
        </table>

        <footer className="mt-5 space-y-0.5 text-xs text-muted">
          {receipt?.reference && <p>Reference: {receipt.reference}</p>}
          <p>Served by {receipt?.received_by_name}</p>
        </footer>
      </article>
    </QueryState>
  )
}

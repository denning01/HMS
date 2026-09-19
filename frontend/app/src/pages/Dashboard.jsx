import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { modulesFor } from '../auth/roles'
import { Alert, PageTitle } from '../components/ui'

export default function Dashboard() {
  const { user } = useAuth()
  const modules = modulesFor(user)

  return (
    <>
      <PageTitle meta={user?.roles?.join(' · ') || 'No role assigned'}>
        {user?.full_name || user?.username}
      </PageTitle>

      {modules.length === 0 && (
        <Alert tone="warn">
          Your account has no role yet, so there is nothing to show. An administrator
          assigns roles under Users &amp; roles.
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {modules.map((item) => {
          const content = (
            <>
              <span className="block text-sm font-semibold text-ink">{item.label}</span>
              <span className="mt-0.5 block text-sm text-muted">{item.description}</span>
            </>
          )

          if (!item.to) {
            return (
              <div key={item.label} className="rounded-xl border border-dashed border-line p-4 opacity-60">
                {content}
                <span className="mt-2 inline-block text-xs text-muted">Not built yet</span>
              </div>
            )
          }

          // Admin pages are Django's own, so they are a full page load.
          if (item.to.startsWith('/admin')) {
            return (
              <a
                key={item.label}
                href={item.to}
                className="rounded-xl border border-line bg-surface p-4 shadow-sm transition-colors hover:border-brand-600"
              >
                {content}
              </a>
            )
          }

          return (
            <Link
              key={item.label}
              to={item.to}
              className="rounded-xl border border-line bg-surface p-4 shadow-sm transition-colors hover:border-brand-600"
            >
              {content}
            </Link>
          )
        })}
      </div>
    </>
  )
}

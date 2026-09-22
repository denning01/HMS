import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { modulesFor } from '../auth/roles'
import { Button } from './ui'

function Nav() {
  const { user } = useAuth()
  // Only what this user can actually reach, so nobody navigates into a 403.
  const links = modulesFor(user).filter((item) => item.to && !item.to.startsWith('/admin'))

  return (
    <nav className="flex items-center gap-1">
      {links.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          // Parents of a deeper route, so they do not stay lit on a child screen.
          end={item.to === '/billing' || item.to === '/pharmacy'}
          className={({ isActive }) =>
            [
              'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              isActive ? 'bg-brand-50 text-brand-700' : 'text-muted hover:text-ink',
            ].join(' ')
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

export default function Layout() {
  const { user, signOut } = useAuth()

  return (
    <div className="min-h-dvh">
      <header className="no-print sticky top-0 z-10 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link to="/" className="text-sm font-semibold tracking-tight text-ink">
            HMS
          </Link>
          <Nav />
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-sm text-muted sm:inline">
              {user?.full_name || user?.username}
            </span>
            <Button variant="secondary" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

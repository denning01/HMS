import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { groupModules, modulesFor } from '../auth/roles'
import { Bars, ChevronDown, Cross, Mark } from './icons'
import { Menu } from './ui'

// Menus only earn their keep once a flat row would not fit. Most roles reach
// three or four screens and want each of them one click away; the Administrator
// reaches fourteen, which has to collapse.
const FLAT_LIMIT = 6

const cx = (...parts) => parts.filter(Boolean).join(' ')

/** The screens this user can actually open, in the order the role map has them. */
function navLinksFor(user) {
  return modulesFor(user).filter((item) => item.to && !item.to.startsWith('/admin'))
}

/**
 * Whether a link should only light up on an exact match.
 *
 * True when another link in the bar sits beneath it — `/lab` next to
 * `/lab/turnaround` — because otherwise the parent stays lit on the child's
 * screen and two things look current at once. A link with no such neighbour
 * stays lit on its own detail pages, which is what you want on
 * `/consultation/41`.
 */
function exactOnly(links, to) {
  return links.some((other) => other.to !== to && other.to.startsWith(`${to}/`))
}

function isCurrent(pathname, item, links) {
  return exactOnly(links, item.to) ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)
}

/* --- the bar ------------------------------------------------------------ */

const LINK = 'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors'
const LINK_ON = 'bg-brand-50 text-brand-700'
const LINK_OFF = 'text-muted hover:bg-canvas hover:text-ink'

function BarLink({ item, links }) {
  return (
    <NavLink
      to={item.to}
      end={exactOnly(links, item.to)}
      className={({ isActive }) => cx(LINK, isActive ? LINK_ON : LINK_OFF)}
    >
      {item.label}
    </NavLink>
  )
}

/** One menu of the bar: its name, and the screens under it. */
function BarMenu({ group, links, pathname }) {
  const current = group.items.some((item) => isCurrent(pathname, item, links))

  return (
    <Menu
      buttonClassName={cx(LINK, 'flex items-center gap-1', current ? LINK_ON : LINK_OFF)}
      label={(open) => (
        <>
          {group.name}
          <ChevronDown className={cx('size-3.5 transition-transform', open && 'rotate-180')} />
        </>
      )}
    >
      {group.items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={exactOnly(links, item.to)}
          className={({ isActive }) =>
            cx(
              'block rounded-lg px-3 py-2 transition-colors',
              isActive ? 'bg-brand-50' : 'hover:bg-canvas',
            )
          }
        >
          <span className={cx('block text-sm font-medium', isCurrent(pathname, item, links) ? 'text-brand-700' : 'text-ink')}>
            {item.label}
          </span>
          <span className="mt-0.5 block text-xs text-muted">{item.description}</span>
        </NavLink>
      ))}
    </Menu>
  )
}

function Nav({ links, pathname }) {
  if (links.length <= FLAT_LIMIT) {
    return (
      <nav className="hidden items-center gap-0.5 md:flex">
        {links.map((item) => (
          <BarLink key={item.to} item={item} links={links} />
        ))}
      </nav>
    )
  }

  return (
    <nav className="hidden items-center gap-0.5 md:flex">
      {groupModules(links).map((group) => (
        <BarMenu key={group.name} group={group} links={links} pathname={pathname} />
      ))}
    </nav>
  )
}

/* --- the same thing on a phone ------------------------------------------ */

function MobileNav({ links, pathname, onNavigate }) {
  return (
    <nav className="border-t border-line bg-surface px-4 py-3 md:hidden">
      {groupModules(links).map((group) => (
        <div key={group.name} className="mb-3 last:mb-0">
          <p className="px-3 pb-1 text-xs font-semibold tracking-wide text-muted uppercase">
            {group.name}
          </p>
          {group.items.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={cx(
                'block rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isCurrent(pathname, item, links) ? 'bg-brand-50 text-brand-700' : 'text-ink hover:bg-canvas',
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  )
}

/* --- who is signed in --------------------------------------------------- */

function initials(name) {
  const words = String(name || '').trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  return (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase()
}

function Account() {
  const { user, signOut } = useAuth()
  const name = user?.full_name || user?.username || ''
  const roles = user?.roles?.join(' · ') || 'No role assigned'

  return (
    <Menu
      align="right"
      buttonClassName={cx(
        'flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-2 pl-1 transition-colors',
        'hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600',
      )}
      label={(open) => (
        <>
          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-semibold text-white">
            {initials(name)}
          </span>
          <span className="hidden max-w-36 truncate text-sm font-medium text-ink sm:inline">{name}</span>
          <ChevronDown className={cx('size-3.5 text-muted transition-transform', open && 'rotate-180')} />
        </>
      )}
    >
      <div className="px-3 py-2">
        <p className="truncate text-sm font-semibold text-ink">{name}</p>
        <p className="mt-0.5 text-xs text-muted">{roles}</p>
      </div>
      <div className="my-1 h-px bg-line" />
      <button
        type="button"
        onClick={signOut}
        className="block w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-ink transition-colors hover:bg-canvas"
      >
        Sign out
      </button>
    </Menu>
  )
}

/* --- the page ----------------------------------------------------------- */

export default function Layout() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  // The phone panel remembers the screen it was opened on, so any move away
  // from it — a link in the panel, or the back button — puts it away.
  const [menu, setMenu] = useState({ open: false, at: pathname })
  const menuOpen = menu.open && menu.at === pathname

  const links = navLinksFor(user)

  return (
    <div className="min-h-dvh">
      <header className="no-print sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-2.5">
          <Link
            to="/"
            className="flex shrink-0 items-center gap-2.5 rounded-lg pr-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
          >
            <Mark className="size-8 rounded-lg" />
            <span className="text-sm leading-tight font-semibold tracking-tight text-ink">
              Hospital
              <span className="block font-normal text-muted">Management System</span>
            </span>
          </Link>

          <div className="mx-2 hidden h-6 w-px bg-line md:block" />

          <Nav links={links} pathname={pathname} />

          <div className="ml-auto flex items-center gap-2">
            <Account />
            {links.length > 0 && (
              <button
                type="button"
                aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={menuOpen}
                onClick={() => setMenu({ open: !menuOpen, at: pathname })}
                className="rounded-lg border border-line p-1.5 text-ink transition-colors hover:bg-canvas md:hidden"
              >
                {menuOpen ? <Cross /> : <Bars />}
              </button>
            )}
          </div>
        </div>

        {menuOpen && (
          <MobileNav links={links} pathname={pathname} onNavigate={() => setMenu({ open: false, at: pathname })} />
        )}
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

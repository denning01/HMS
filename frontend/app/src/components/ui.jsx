// The small vocabulary every screen is built from. Kept in one file because it
// is small; the moment any one of these needs its own tests it moves out.

import { Link } from 'react-router-dom'

const cx = (...parts) => parts.filter(Boolean).join(' ')

/* --- surfaces ----------------------------------------------------------- */

export function Card({ title, actions, children, className }) {
  return (
    <section className={cx('rounded-xl border border-line bg-surface shadow-sm', className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}

export function Rows({ children }) {
  return <ul className="divide-y divide-line">{children}</ul>
}

export function Row({ children, className }) {
  return <li className={cx('flex items-center justify-between gap-4 px-4 py-3', className)}>{children}</li>
}

export function Empty({ children }) {
  return <p className="px-4 py-8 text-center text-sm text-muted">{children}</p>
}

/* --- type --------------------------------------------------------------- */

export function PageTitle({ children, meta }) {
  return (
    <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
      <h1 className="text-xl font-semibold tracking-tight text-ink">{children}</h1>
      {meta && <span className="text-sm text-muted">{meta}</span>}
    </div>
  )
}

/** Money always renders with the unit and two decimals, aligned column to column. */
export function Money({ value, className }) {
  const amount = Number(value ?? 0).toLocaleString('en-KE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return <span className={cx('tabular', className)}>KES {amount}</span>
}

const TONES = {
  neutral: 'bg-brand-50 text-brand-700',
  good: 'bg-good-bg text-good',
  warn: 'bg-warn-bg text-warn',
  danger: 'bg-danger-bg text-danger',
  quiet: 'bg-canvas text-muted',
}

export function Badge({ tone = 'neutral', children }) {
  return (
    <span className={cx('rounded-full px-2 py-0.5 text-xs font-medium', TONES[tone])}>
      {children}
    </span>
  )
}

/* --- controls ----------------------------------------------------------- */

const BUTTONS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/40',
  secondary: 'border border-line bg-surface text-ink hover:bg-canvas disabled:opacity-50',
  quiet: 'text-brand-700 hover:bg-brand-50 disabled:opacity-50',
}

export function Button({ variant = 'primary', className, as, to, ...props }) {
  const classes = cx(
    'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium',
    'transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600',
    'disabled:cursor-not-allowed',
    BUTTONS[variant],
    className,
  )

  if (as === 'link') return <Link to={to} className={classes} {...props} />
  return <button type="button" className={classes} {...props} />
}

export function Field({ label, error, hint, children, className }) {
  return (
    <label className={cx('block', className)}>
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && (
        <span role="alert" className="mt-1 block text-xs text-danger">
          {error}
        </span>
      )}
    </label>
  )
}

const CONTROL =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink ' +
  'placeholder:text-muted focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100'

export function Input({ className, invalid, ...props }) {
  return <input className={cx(CONTROL, invalid && 'border-danger', className)} {...props} />
}

export function Select({ className, invalid, children, ...props }) {
  return (
    <select className={cx(CONTROL, invalid && 'border-danger', className)} {...props}>
      {children}
    </select>
  )
}

export function Textarea({ className, ...props }) {
  return <textarea className={cx(CONTROL, className)} {...props} />
}

/* --- state -------------------------------------------------------------- */

export function Alert({ tone = 'danger', children }) {
  if (!children) return null
  const tones = {
    danger: 'border-danger/30 bg-danger-bg text-danger',
    warn: 'border-warn/30 bg-warn-bg text-warn',
    good: 'border-good/30 bg-good-bg text-good',
  }
  return (
    <div role="alert" className={cx('mb-4 rounded-lg border px-3.5 py-2.5 text-sm', tones[tone])}>
      {children}
    </div>
  )
}

export function Loading({ label = 'Loading…' }) {
  return (
    <p className="px-4 py-10 text-center text-sm text-muted" aria-live="polite">
      {label}
    </p>
  )
}

/** Every screen reports a failed load the same way, rather than rendering blank. */
export function QueryState({ query, children, empty }) {
  if (query.isPending) return <Loading />
  if (query.isError) return <Alert>{query.error.message}</Alert>
  if (empty && empty(query.data)) return <Empty>{empty(query.data)}</Empty>
  return children
}

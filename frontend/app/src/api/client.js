// One place that talks to Django.
//
// Session cookies carry the identity, so nothing is stored in the browser and
// every request just needs `credentials: same-origin` and, for unsafe methods,
// the CSRF token Django set as a cookie.

function readCookie(name) {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.split('=')[1]
}

/** Fired when the server says nobody is signed in. The auth provider listens. */
export const SIGNED_OUT = 'hms:signed-out'

/** Thrown for any non-2xx response, carrying what the server said. */
export class ApiError extends Error {
  constructor(status, body) {
    // DRF reports either {detail: "..."} or {field: ["..."]}; both should read
    // as a sentence when a screen shows the error without unpacking it.
    const detail =
      body?.detail ??
      (body && typeof body === 'object'
        ? Object.values(body).flat().join(' ')
        : null)
    super(detail || `Request failed (${status})`)
    this.status = status
    this.body = body ?? {}
    /** Field errors, for a form to show against its inputs. */
    this.fields = body && typeof body === 'object' && !body.detail ? body : {}
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') {
    const token = readCookie('csrftoken')
    if (token) headers['X-CSRFToken'] = token
  }

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })

  // 401 is the session having run out, not a screen refusing. Announced once,
  // here, so no screen has to handle it and none can forget to.
  if (response.status === 401) window.dispatchEvent(new CustomEvent(SIGNED_OUT))

  if (response.status === 204) return null

  const text = await response.text()
  const payload = text ? JSON.parse(text) : null

  if (!response.ok) throw new ApiError(response.status, payload)
  return payload
}

export const api = {
  get: (path, options) => request(path, options),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  // Administration edits one field at a time — a price, a reorder level, a set
  // of roles — so they are sent as a patch rather than a whole record the
  // screen would have to hold and could overwrite from stale state.
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),

  /** Called once on boot so the first POST of the session has a CSRF token. */
  primeCsrf: () => request('/auth/csrf/'),
}

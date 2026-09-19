import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import { AuthContext } from './context'

/**
 * Who is signed in.
 *
 * The session lives in an httpOnly cookie, so the client cannot read it and has
 * to ask. Until that answer arrives nothing renders, otherwise a reload would
 * flash the login screen at someone who is already signed in.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    let cancelled = false

    async function restore() {
      try {
        await api.primeCsrf()
        const me = await api.get('/auth/me/')
        if (!cancelled) setUser(me)
      } catch (error) {
        // 403 here just means "not signed in", which is not an error to report.
        if (!cancelled && !(error instanceof ApiError)) console.error(error)
      } finally {
        if (!cancelled) setReady(true)
      }
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [])

  async function signIn(username, password) {
    const me = await api.post('/auth/login/', { username, password })
    setUser(me)
    return me
  }

  async function signOut() {
    await api.post('/auth/logout/')
    setUser(null)
    // Another user may sign in at the same terminal; nothing of this one's
    // should still be cached when they do.
    queryClient.clear()
  }

  return (
    <AuthContext.Provider value={{ user, ready, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

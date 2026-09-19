import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import { ApiError } from './api/client'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      // Retrying a 403 or a 404 only delays the message the user needs to see.
      retry: (failureCount, error) =>
        error instanceof ApiError && error.status < 500 ? false : failureCount < 2,
      refetchOnWindowFocus: true,
    },
    mutations: { retry: false },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)

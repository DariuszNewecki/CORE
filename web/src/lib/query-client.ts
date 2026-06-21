import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) => {
        if (
          error &&
          typeof error === 'object' &&
          'status' in error &&
          (error as { status: number }).status === 401
        ) {
          return false
        }
        return count < 2
      },
    },
  },
})

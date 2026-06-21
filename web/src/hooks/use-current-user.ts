import { useMeAuthMeGet } from '@/api'

export function useCurrentUser() {
  return useMeAuthMeGet({ query: { retry: false, staleTime: 60_000 } })
}

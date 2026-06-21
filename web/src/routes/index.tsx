import { createFileRoute, redirect } from '@tanstack/react-router'
import { meAuthMeGet } from '@/api'

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    try {
      await meAuthMeGet()
      throw redirect({ to: '/dashboard' })
    } catch (e) {
      if (e && typeof e === 'object' && 'to' in e) throw e
      throw redirect({ to: '/login' })
    }
  },
})

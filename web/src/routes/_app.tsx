import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { meAuthMeGet } from '@/api'

export const Route = createFileRoute('/_app')({
  beforeLoad: async () => {
    try {
      await meAuthMeGet()
    } catch {
      throw redirect({ to: '/login' })
    }
  },
  component: AppLayout,
})

function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Outlet />
    </div>
  )
}

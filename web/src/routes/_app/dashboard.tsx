import { createFileRoute } from '@tanstack/react-router'
import { useLogoutAuthLogoutPost } from '@/api'
import { useCurrentUser } from '@/hooks/use-current-user'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/_app/dashboard')({
  component: DashboardPage,
})

function DashboardPage() {
  const { data: user } = useCurrentUser()
  const logout = useLogoutAuthLogoutPost()

  async function handleLogout() {
    await logout.mutateAsync()
    window.location.href = '/login'
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <span className="font-semibold tracking-tight">CORE</span>
        <div className="flex items-center gap-4">
          {user && typeof user === 'object' && 'email' in user && (
            <span className="text-sm text-muted-foreground">{String(user.email)}</span>
          )}
          <Button variant="outline" size="sm" onClick={handleLogout} disabled={logout.isPending}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="flex-1 p-6">
        <h2 className="text-xl font-semibold">Dashboard</h2>
        <p className="mt-2 text-sm text-muted-foreground">Welcome to CORE.</p>
      </main>
    </div>
  )
}

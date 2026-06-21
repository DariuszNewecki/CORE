import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_public')({
  component: PublicLayout,
})

function PublicLayout() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">CORE</h1>
          <p className="mt-1 text-sm text-muted-foreground">Constitutional governance platform</p>
        </div>
        <Outlet />
      </div>
    </div>
  )
}

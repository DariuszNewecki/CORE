import { useEffect, useState } from 'react'
import { createFileRoute, Link } from '@tanstack/react-router'
import { z } from 'zod'
import { apiFetch } from '@/lib/fetch-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/_public/verify-email')({
  validateSearch: z.object({ token: z.string() }),
  component: VerifyEmailPage,
})

function VerifyEmailPage() {
  const { token } = Route.useSearch()
  const [state, setState] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    apiFetch<{ message: string }>(
      `/auth/verify-email?token=${encodeURIComponent(token)}`,
    )
      .then(() => setState('success'))
      .catch((err: unknown) => {
        const detail =
          err && typeof err === 'object' && 'detail' in err
            ? String((err as { detail: unknown }).detail)
            : 'Verification failed. The link may have expired.'
        setErrorMsg(detail)
        setState('error')
      })
  }, [token])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Email verification</CardTitle>
        <CardDescription>
          {state === 'loading' && 'Verifying your email address…'}
          {state === 'success' && 'Your email address has been verified.'}
          {state === 'error' && 'Verification failed.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {state === 'loading' && (
          <p className="text-sm text-muted-foreground">Please wait…</p>
        )}
        {state === 'success' && (
          <>
            <p className="text-sm text-muted-foreground">
              You can now sign in to your CORE account.
            </p>
            <Button asChild className="w-full">
              <Link to="/login">Go to sign in</Link>
            </Button>
          </>
        )}
        {state === 'error' && (
          <>
            <p className="text-sm text-destructive">{errorMsg}</p>
            <p className="text-center text-sm text-muted-foreground">
              <Link to="/login" className="text-foreground hover:underline underline-offset-4">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

import { createFileRoute, Link, useRouter, useSearch } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { usePasswordResetConfirmAuthPasswordResetConfirmPost } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'

export const Route = createFileRoute('/_public/reset-password')({
  validateSearch: z.object({ token: z.string() }),
  component: ResetPasswordPage,
})

const schema = z.object({
  new_password: z.string().min(12, 'Password must be at least 12 characters'),
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, {
  message: 'Passwords do not match',
  path: ['confirm'],
})

type FormValues = z.infer<typeof schema>

function ResetPasswordPage() {
  const router = useRouter()
  const { token } = useSearch({ from: '/_public/reset-password' })
  const confirm = usePasswordResetConfirmAuthPasswordResetConfirmPost()

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: '', confirm: '' },
  })

  async function onSubmit(values: FormValues) {
    await confirm.mutateAsync(
      { data: { token, new_password: values.new_password } },
      { onSuccess: () => router.navigate({ to: '/login' }) },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Set new password</CardTitle>
        <CardDescription>Choose a strong password of at least 12 characters.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirm"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {confirm.error && (
              <p className="text-sm text-destructive">
                {typeof confirm.error === 'object' && confirm.error !== null && 'detail' in confirm.error
                  ? String((confirm.error as { detail: unknown }).detail)
                  : 'Reset failed. The link may have expired.'}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={confirm.isPending}>
              {confirm.isPending ? 'Saving…' : 'Set password'}
            </Button>
          </form>
        </Form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link to="/login" className="text-foreground hover:underline underline-offset-4">
            Back to sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}

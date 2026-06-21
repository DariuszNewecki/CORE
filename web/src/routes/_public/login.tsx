import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useLoginAuthLoginPost } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'

export const Route = createFileRoute('/_public/login')({
  component: LoginPage,
})

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type FormValues = z.infer<typeof schema>

function LoginPage() {
  const router = useRouter()
  const login = useLoginAuthLoginPost()

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  })

  async function onSubmit(values: FormValues) {
    await login.mutateAsync(
      { data: values },
      { onSuccess: () => router.navigate({ to: '/dashboard' }) },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Enter your credentials to continue</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" placeholder="you@example.com" autoComplete="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="current-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {login.error && (
              <p className="text-sm text-destructive">
                {typeof login.error === 'object' && login.error !== null && 'detail' in login.error
                  ? String((login.error as { detail: unknown }).detail)
                  : 'Invalid credentials.'}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </Form>
        <div className="mt-4 space-y-2 text-center text-sm">
          <p>
            <Link to="/forgot-password" className="text-muted-foreground hover:text-foreground underline underline-offset-4">
              Forgot password?
            </Link>
          </p>
          <p className="text-muted-foreground">
            No account?{' '}
            <Link to="/register" className="text-foreground hover:underline underline-offset-4">
              Create one
            </Link>
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

import { createFileRoute, Link, useRouter, useSearch } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRegisterAuthRegisterPost } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'

export const Route = createFileRoute('/_public/register')({
  validateSearch: z.object({ token: z.string().optional() }),
  component: RegisterPage,
})

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(12, 'Password must be at least 12 characters'),
  org_name: z.string().min(2, 'Organisation name is required').optional().or(z.literal('')),
})

type FormValues = z.infer<typeof schema>

function RegisterPage() {
  const router = useRouter()
  const { token } = useSearch({ from: '/_public/register' })
  const register = useRegisterAuthRegisterPost()

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '', org_name: '' },
  })

  async function onSubmit(values: FormValues) {
    await register.mutateAsync(
      {
        data: {
          email: values.email,
          password: values.password,
          org_name: values.org_name || undefined,
          invitation_token: token,
        },
      },
      { onSuccess: () => router.navigate({ to: '/dashboard' }) },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create account</CardTitle>
        <CardDescription>
          {token ? 'Complete your invitation to join CORE.' : 'Start your CORE organisation.'}
        </CardDescription>
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
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {!token && (
              <FormField
                control={form.control}
                name="org_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Organisation name</FormLabel>
                    <FormControl>
                      <Input placeholder="Acme Corp" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
            {register.error && (
              <p className="text-sm text-destructive">
                {typeof register.error === 'object' && register.error !== null && 'detail' in register.error
                  ? String((register.error as { detail: unknown }).detail)
                  : 'Registration failed. Please try again.'}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={register.isPending}>
              {register.isPending ? 'Creating account…' : 'Create account'}
            </Button>
          </form>
        </Form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="text-foreground hover:underline underline-offset-4">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}

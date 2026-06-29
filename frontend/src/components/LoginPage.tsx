import { FormEvent, useState } from 'react'
import { LogIn } from 'lucide-react'

import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await login(email, password)
    } catch {
      setError('邮箱或密码不正确。')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-screen">
      <section className="login-panel" aria-label="登录">
        <div className="brand login-brand">
          <span className="brand-mark" aria-hidden="true" />
          <span>Lumen</span>
        </div>
        <p className="eyebrow">账户访问</p>
        <h1>登录 Lumen</h1>
        <form className="login-form" onSubmit={submit}>
          <label className="field-label" htmlFor="login-email">
            邮箱
          </label>
          <input
            autoComplete="email"
            id="login-email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
          <label className="field-label" htmlFor="login-password">
            密码
          </label>
          <input
            autoComplete="current-password"
            id="login-password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-action" disabled={isSubmitting} type="submit">
            <LogIn size={18} strokeWidth={1.9} aria-hidden="true" />
            <span>{isSubmitting ? '登录中' : '登录'}</span>
          </button>
        </form>
      </section>
    </main>
  )
}

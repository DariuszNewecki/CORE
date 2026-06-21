// Orval mutator + single-flight refresh (ADR-125 D12).
// Orval calls apiFetch<T>(url, options) and expects Promise<T> — this
// function owns fetch, 401-refresh, JSON parsing, and error surfacing.
let _refreshPromise: Promise<boolean> | null = null

async function _doRefresh(): Promise<boolean> {
  const resp = await fetch('/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  })
  return resp.ok
}

export async function apiFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const execute = () => fetch(url, { credentials: 'include', ...options })

  let resp = await execute()

  if (resp.status === 401) {
    if (_refreshPromise === null) {
      _refreshPromise = _doRefresh().finally(() => {
        _refreshPromise = null
      })
    }
    const refreshed = await _refreshPromise
    if (!refreshed) {
      throw Object.assign(new Error('session_expired'), { status: 401 })
    }
    resp = await execute()
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw body
  }

  if (resp.status === 204 || resp.headers.get('content-length') === '0') {
    return undefined as T
  }

  return resp.json() as Promise<T>
}

import { toast } from 'sonner'
import i18n from '@/lib/i18n'

export function createApiClient(baseUrl) {
  async function request(method, path, { body, timeout = 30000, silent = false } = {}) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const options = {
        method,
        signal: controller.signal,
        headers: {},
      }

      if (body !== undefined) {
        options.headers['Content-Type'] = 'application/json'
        options.body = JSON.stringify(body)
      }

      if (import.meta.env.VITE_EMBEDDED !== 'true') {
        options.targetAddressSpace = 'local'
      }
      const response = await fetch(`${baseUrl}${path}`, options)
      const json = await response.json()

      if (!response.ok) {
        const err = new Error(json.error?.message || `HTTP ${response.status}`)
        err.details = json.error?.details
        err.status = response.status
        throw err
      }

      return json.data
    } catch (error) {
      if (error.name === 'AbortError') {
        if (!silent) {
          toast.error(i18n.t('errors.timeout'))
        }
        throw new Error(i18n.t('errors.timeout'))
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }

  return {
    get: (path, opts) => request('GET', path, opts),
    post: (path, body, opts) => request('POST', path, { body, ...opts }),
    put: (path, body, opts) => request('PUT', path, { body, ...opts }),
    delete: (path, opts) => request('DELETE', path, opts),
  }
}

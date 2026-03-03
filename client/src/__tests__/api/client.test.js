import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import { createApiClient } from '@/api/client'

const BASE = 'http://test-device'

describe('createApiClient', () => {
  it('unwraps successful response data', async () => {
    server.use(
      http.get(`${BASE}/test`, () =>
        HttpResponse.json({ data: { foo: 'bar' }, error: null })
      )
    )
    const client = createApiClient(BASE)
    const result = await client.get('/test')
    expect(result).toEqual({ foo: 'bar' })
  })

  it('throws on error response', async () => {
    server.use(
      http.get(`${BASE}/test`, () =>
        HttpResponse.json(
          { data: null, error: { message: 'Not found', details: null } },
          { status: 404 }
        )
      )
    )
    const client = createApiClient(BASE)
    await expect(client.get('/test')).rejects.toThrow('Not found')
  })

  it('sends JSON body on PUT', async () => {
    let receivedBody = null
    server.use(
      http.put(`${BASE}/test`, async ({ request }) => {
        receivedBody = await request.json()
        return HttpResponse.json({ data: 'ok', error: null })
      })
    )
    const client = createApiClient(BASE)
    await client.put('/test', { key: 'value' })
    expect(receivedBody).toEqual({ key: 'value' })
  })

  it('sends JSON body on POST', async () => {
    let receivedBody = null
    server.use(
      http.post(`${BASE}/test`, async ({ request }) => {
        receivedBody = await request.json()
        return HttpResponse.json({ data: 'ok', error: null })
      })
    )
    const client = createApiClient(BASE)
    await client.post('/test', { action: 'do' })
    expect(receivedBody).toEqual({ action: 'do' })
  })
})

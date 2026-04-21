import { describe, it, expect, beforeEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import { useServicesStore } from '@/stores/services'
import { useConnectionStore } from '@/stores/connection'
import { createApiClient } from '@/api/client'

const BASE = 'http://test-device'

function ok(data) {
  return HttpResponse.json({ data, error: null })
}

describe('useServicesStore', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
    useServicesStore.setState({
      services: [],
      loading: false,
      error: null,
      actionsInProgress: {},
      logContent: null,
      logServiceName: null,
      logLoading: false,
    })
  })

  it('fetches services', async () => {
    await useServicesStore.getState().fetchServices()
    const { services } = useServicesStore.getState()
    expect(services.length).toBeGreaterThan(0)
    expect(services[0]).toHaveProperty('name')
    expect(services[0]).toHaveProperty('type')
    expect(services[0]).toHaveProperty('state')
  })

  it('returns early when no apiClient is available', async () => {
    useConnectionStore.setState({ apiClient: null })
    await useServicesStore.getState().fetchServices()
    expect(useServicesStore.getState().services).toEqual([])
    expect(useServicesStore.getState().loading).toBe(false)
  })

  it('reports service active status correctly', async () => {
    await useServicesStore.getState().fetchServices()
    const store = useServicesStore.getState()
    expect(store.isServiceActive('v3xctrl-video')).toBe(true)
    expect(store.isServiceActive('v3xctrl-control')).toBe(false)
  })

  it('reports service inactive status correctly', async () => {
    await useServicesStore.getState().fetchServices()
    const store = useServicesStore.getState()
    expect(store.isServiceInactive('v3xctrl-control')).toBe(true)
    expect(store.isServiceInactive('v3xctrl-video')).toBe(false)
  })

  it('returns falsy for unknown service name', async () => {
    await useServicesStore.getState().fetchServices()
    const store = useServicesStore.getState()
    expect(store.isServiceActive('nonexistent')).toBe(false)
    expect(store.isServiceInactive('nonexistent')).toBeTruthy()
  })

  it('fetches service log', async () => {
    await useServicesStore.getState().fetchLog('v3xctrl-video')
    const { logContent, logServiceName } = useServicesStore.getState()
    expect(logContent).toContain('test log line')
    expect(logServiceName).toBe('v3xctrl-video')
  })

  it('sets logLoading during log fetch', async () => {
    const snapshots = []
    const unsubscribe = useServicesStore.subscribe((state) => {
      snapshots.push({ logLoading: state.logLoading })
    })

    await useServicesStore.getState().fetchLog('v3xctrl-video')
    unsubscribe()

    expect(snapshots[0].logLoading).toBe(true)
    expect(useServicesStore.getState().logLoading).toBe(false)
  })

  it('clears log state on fetchLog error', async () => {
    server.use(
      http.get(`${BASE}/service/:name/log`, () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    await useServicesStore.getState().fetchLog('v3xctrl-video')
    const { logContent, logServiceName, logLoading } = useServicesStore.getState()
    expect(logContent).toBeNull()
    expect(logServiceName).toBeNull()
    expect(logLoading).toBe(false)
  })

  it('clears log', async () => {
    await useServicesStore.getState().fetchLog('v3xctrl-video')
    useServicesStore.getState().clearLog()
    const { logContent, logServiceName } = useServicesStore.getState()
    expect(logContent).toBeNull()
    expect(logServiceName).toBeNull()
  })

  it('sets and clears actionsInProgress during startService', async () => {
    await useServicesStore.getState().fetchServices()

    server.use(
      http.get(`${BASE}/service/:name`, ({ params }) =>
        ok({ name: params.name, type: 'simple', state: 'active', result: 'success' }),
      ),
    )

    const snapshots = []
    const unsubscribe = useServicesStore.subscribe((state) => {
      snapshots.push({ ...state.actionsInProgress })
    })

    await useServicesStore.getState().startService('v3xctrl-control')
    unsubscribe()

    expect(snapshots.some((s) => s['v3xctrl-control'] === true)).toBe(true)
    expect(useServicesStore.getState().actionsInProgress).toEqual({})
  }, 15000)

  it('polls and updates individual service state after action', async () => {
    await useServicesStore.getState().fetchServices()

    server.use(
      http.get(`${BASE}/service/:name`, ({ params }) =>
        ok({ name: params.name, type: 'simple', state: 'active', result: 'success' }),
      ),
    )

    await useServicesStore.getState().startService('v3xctrl-control')

    const service = useServicesStore.getState().services.find((s) => s.name === 'v3xctrl-control')
    expect(service.state).toBe('active')
  }, 15000)

  it('clears actionsInProgress on API error', async () => {
    server.use(
      http.post(`${BASE}/service/:name/start`, () =>
        new HttpResponse(JSON.stringify({ data: null, error: 'fail' }), { status: 500 }),
      ),
    )

    await expect(useServicesStore.getState().startService('v3xctrl-control')).rejects.toThrow()
    expect(useServicesStore.getState().actionsInProgress).toEqual({})
  })

  it('stops a service and polls until inactive', async () => {
    await useServicesStore.getState().fetchServices()

    server.use(
      http.get(`${BASE}/service/:name`, ({ params }) =>
        ok({ name: params.name, type: 'simple', state: 'inactive', result: 'success' }),
      ),
    )

    await useServicesStore.getState().stopService('v3xctrl-video')

    const service = useServicesStore.getState().services.find((s) => s.name === 'v3xctrl-video')
    expect(service.state).toBe('inactive')
    expect(useServicesStore.getState().actionsInProgress).toEqual({})
  }, 15000)

  it('restarts a service and polls until active', async () => {
    await useServicesStore.getState().fetchServices()

    server.use(
      http.get(`${BASE}/service/:name`, ({ params }) =>
        ok({ name: params.name, type: 'simple', state: 'active', result: 'success' }),
      ),
    )

    await useServicesStore.getState().restartService('v3xctrl-video')

    const service = useServicesStore.getState().services.find((s) => s.name === 'v3xctrl-video')
    expect(service.state).toBe('active')
    expect(useServicesStore.getState().actionsInProgress).toEqual({})
  }, 15000)

  it('handles fetchServices error', async () => {
    server.use(
      http.get(`${BASE}/service`, () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    await useServicesStore.getState().fetchServices()
    const { error, loading } = useServicesStore.getState()
    expect(error).toBeTruthy()
    expect(loading).toBe(false)
  })
})

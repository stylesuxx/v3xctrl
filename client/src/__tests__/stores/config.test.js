import { describe, it, expect, beforeEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import { useConfigStore } from '@/stores/config'
import { useConnectionStore } from '@/stores/connection'
import { createApiClient } from '@/api/client'
import { mockConfig } from '../mocks/data'

const BASE = 'http://test-device'

describe('useConfigStore', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
    useConfigStore.setState({
      config: null,
      schema: null,
      modems: null,
      loading: false,
      error: null,
      previousModel: null,
    })
  })

  it('fetches config, schema, and modems', async () => {
    await useConfigStore.getState().fetchConfig()
    const { config, schema, modems, loading } = useConfigStore.getState()
    expect(config).not.toBeNull()
    expect(schema).not.toBeNull()
    expect(modems).not.toBeNull()
    expect(loading).toBe(false)
  })

  it('sets previousModel from fetched config', async () => {
    await useConfigStore.getState().fetchConfig()
    const { previousModel } = useConfigStore.getState()
    expect(previousModel).toBe('generic')
  })

  it('returns valid bands for a modem model', async () => {
    await useConfigStore.getState().fetchConfig()
    const bands = useConfigStore.getState().getValidBands('generic')
    expect(Array.isArray(bands)).toBe(true)
    expect(bands.length).toBeGreaterThan(0)
  })

  it('returns generic bands for unknown model', async () => {
    await useConfigStore.getState().fetchConfig()
    const bands = useConfigStore.getState().getValidBands('nonexistent-model')
    expect(Array.isArray(bands)).toBe(true)
  })

  it('returns empty bands when modems not loaded', () => {
    const bands = useConfigStore.getState().getValidBands('generic')
    expect(bands).toEqual([])
  })

  it('updates config', () => {
    const newConfig = { test: true }
    useConfigStore.getState().updateConfig(newConfig)
    expect(useConfigStore.getState().config).toEqual(newConfig)
  })

  it('saves config successfully', async () => {
    const configData = structuredClone(mockConfig)
    await useConfigStore.getState().saveConfig(configData)
    expect(useConfigStore.getState().config).toEqual(configData)
  })

  it('sets error and rethrows on save failure', async () => {
    server.use(
      http.put(`${BASE}/config`, () =>
        new HttpResponse(
          JSON.stringify({ data: null, error: { message: 'Write failed' } }),
          { status: 500 },
        ),
      ),
    )

    await expect(useConfigStore.getState().saveConfig(mockConfig)).rejects.toThrow()
    expect(useConfigStore.getState().error).toBeTruthy()
  })

  it('sets error on fetch failure', async () => {
    server.use(
      http.get(`${BASE}/config`, () =>
        new HttpResponse(
          JSON.stringify({ data: null, error: { message: 'Server error' } }),
          { status: 500 },
        ),
      ),
    )

    await useConfigStore.getState().fetchConfig()
    const { error, loading } = useConfigStore.getState()
    expect(error).toBeTruthy()
    expect(loading).toBe(false)
  })

  it('does nothing when apiClient is null', async () => {
    useConnectionStore.setState({ apiClient: null })
    await useConfigStore.getState().fetchConfig()
    expect(useConfigStore.getState().loading).toBe(false)
  })

  it('sets loading to true during fetch', async () => {
    const snapshots = []
    const unsubscribe = useConfigStore.subscribe((state) => {
      snapshots.push(state.loading)
    })

    await useConfigStore.getState().fetchConfig()
    unsubscribe()

    expect(snapshots[0]).toBe(true)
  })
})

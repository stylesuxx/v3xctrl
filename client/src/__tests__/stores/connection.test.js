import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import { useConnectionStore } from '@/stores/connection'
import { mockInfo } from '../mocks/data'

const BASE = 'http://test-device'

function ok(data) {
  return HttpResponse.json({ data, error: null })
}

describe('useConnectionStore', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      deviceUrl: null,
      deviceHostname: null,
      apiClient: null,
      connected: false,
      connecting: false,
      connectionError: null,
      isScanning: false,
      discoveredDevices: [],
      scanProgress: 0,
    })
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('connect', () => {
    it('connects successfully and updates state', async () => {
      await useConnectionStore.getState().connect(BASE)

      const state = useConnectionStore.getState()
      expect(state.connected).toBe(true)
      expect(state.connecting).toBe(false)
      expect(state.deviceUrl).toBe(BASE)
      expect(state.deviceHostname).toBe('test-streamer')
      expect(state.apiClient).not.toBeNull()
      expect(state.connectionError).toBeNull()
    })

    it('persists device URL to localStorage', async () => {
      await useConnectionStore.getState().connect(BASE)
      expect(localStorage.getItem('v3xctrl-last-device')).toBe(BASE)
    })

    it('sets connecting state during connection attempt', async () => {
      const snapshots = []
      const unsubscribe = useConnectionStore.subscribe((state) => {
        snapshots.push({ connecting: state.connecting, connected: state.connected })
      })

      await useConnectionStore.getState().connect(BASE)
      unsubscribe()

      expect(snapshots[0].connecting).toBe(true)
      expect(snapshots[0].connected).toBe(false)
    })

    it('sets connectionError on failure and throws', async () => {
      server.use(
        http.get(`${BASE}/system/info`, () =>
          new HttpResponse(null, { status: 500 }),
        ),
      )

      await expect(useConnectionStore.getState().connect(BASE)).rejects.toThrow('unreachable')

      const state = useConnectionStore.getState()
      expect(state.connecting).toBe(false)
      expect(state.connected).toBe(false)
      expect(state.connectionError).toBe(BASE)
    })

    it('handles missing hostname gracefully', async () => {
      server.use(
        http.get(`${BASE}/system/info`, () => ok({})),
      )

      await useConnectionStore.getState().connect(BASE)
      expect(useConnectionStore.getState().deviceHostname).toBeNull()
    })
  })

  describe('disconnect', () => {
    it('clears connection state', async () => {
      await useConnectionStore.getState().connect(BASE)
      expect(useConnectionStore.getState().connected).toBe(true)

      useConnectionStore.getState().disconnect()

      const state = useConnectionStore.getState()
      expect(state.connected).toBe(false)
      expect(state.deviceUrl).toBeNull()
      expect(state.deviceHostname).toBeNull()
      expect(state.apiClient).toBeNull()
    })
  })

  describe('getLastDevice', () => {
    it('returns null when no device stored', () => {
      expect(useConnectionStore.getState().getLastDevice()).toBeNull()
    })

    it('returns stored device URL', async () => {
      await useConnectionStore.getState().connect(BASE)
      expect(useConnectionStore.getState().getLastDevice()).toBe(BASE)
    })
  })

  describe('connectEmbedded', () => {
    const origin = window.location.origin

    it('connects using window.location.origin', async () => {
      server.use(
        http.get(`${origin}/system/info`, () => ok(mockInfo)),
      )

      await useConnectionStore.getState().connectEmbedded()

      const state = useConnectionStore.getState()
      expect(state.connected).toBe(true)
      expect(state.deviceUrl).toBe(origin)
      expect(state.deviceHostname).toBe('test-streamer')
    })

    it('does not persist to localStorage', async () => {
      server.use(
        http.get(`${origin}/system/info`, () => ok(mockInfo)),
      )

      await useConnectionStore.getState().connectEmbedded()
      expect(localStorage.getItem('v3xctrl-last-device')).toBeNull()
    })

    it('sets connectionError on failure and throws', async () => {
      server.use(
        http.get(`${origin}/system/info`, () =>
          new HttpResponse(null, { status: 500 }),
        ),
      )

      await expect(useConnectionStore.getState().connectEmbedded()).rejects.toThrow('unreachable')

      const state = useConnectionStore.getState()
      expect(state.connecting).toBe(false)
      expect(state.connectionError).toBe(origin)
    })
  })

  describe('scanSubnet', () => {
    it('sets scanning state during scan', async () => {
      const snapshots = []
      const unsubscribe = useConnectionStore.subscribe((state) => {
        if (state.isScanning !== snapshots[snapshots.length - 1]?.isScanning) {
          snapshots.push({ isScanning: state.isScanning })
        }
      })

      // Mock all fetch calls to fail quickly (no devices found)
      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('timeout'))

      await useConnectionStore.getState().scanSubnet('192.168.1')
      unsubscribe()

      expect(snapshots[0]?.isScanning).toBe(true)
      expect(useConnectionStore.getState().isScanning).toBe(false)
    })

    it('discovers devices that respond', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
        if (url === 'http://192.168.1.42/system/info') {
          return new Response(JSON.stringify({ data: mockInfo }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        throw new Error('timeout')
      })

      await useConnectionStore.getState().scanSubnet('192.168.1')

      const { discoveredDevices } = useConnectionStore.getState()
      expect(discoveredDevices).toHaveLength(1)
      expect(discoveredDevices[0].ip).toBe('192.168.1.42')
      expect(discoveredDevices[0].url).toBe('http://192.168.1.42')
    })

    it('tracks scan progress', async () => {
      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('timeout'))

      await useConnectionStore.getState().scanSubnet('192.168.1')

      // All 254 IPs should have been processed
      expect(useConnectionStore.getState().scanProgress).toBe(254)
    })

    it('ignores hosts that return invalid data', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
        return new Response(JSON.stringify({ error: 'not v3xctrl' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      })

      await useConnectionStore.getState().scanSubnet('192.168.1')
      expect(useConnectionStore.getState().discoveredDevices).toHaveLength(0)
    })
  })
})

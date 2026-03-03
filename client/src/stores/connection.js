import { create } from 'zustand'
import { createApiClient } from '@/api/client'

export const useConnectionStore = create((set) => ({
  deviceUrl: null,
  deviceHostname: null,
  apiClient: null,
  connected: false,
  connecting: false,
  connectionError: null,

  isScanning: false,
  discoveredDevices: [],
  scanProgress: 0,

  connectEmbedded: async () => {
    const url = window.location.origin
    const client = createApiClient(url)
    set({ connecting: true, connectionError: null })
    try {
      const info = await client.get('/system/info', { timeout: 3000, silent: true })
      set({ deviceUrl: url, deviceHostname: info?.hostname || null, apiClient: client, connected: true, connecting: false })
    } catch {
      set({ connecting: false, connectionError: url })
      throw new Error('unreachable')
    }
  },

  connect: async (url, { silent = false } = {}) => {
    const client = createApiClient(url)
    set({ connecting: true, connectionError: null })
    try {
      const info = await client.get('/system/info', { timeout: 3000, silent })
      set({ deviceUrl: url, deviceHostname: info?.hostname || null, apiClient: client, connected: true, connecting: false })
      localStorage.setItem('v3xctrl-last-device', url)
    } catch {
      set({ connecting: false, connectionError: url })
      throw new Error('unreachable')
    }
  },

  disconnect: () => {
    set({ deviceUrl: null, deviceHostname: null, apiClient: null, connected: false })
    history.replaceState(null, null, ' ')
  },

  getLastDevice: () => {
    return localStorage.getItem('v3xctrl-last-device')
  },

  scanSubnet: async (subnetBase) => {
    set({ isScanning: true, discoveredDevices: [], scanProgress: 0 })

    const BATCH_SIZE = 30
    const ips = []
    for (let i = 1; i <= 254; i++) {
      ips.push(`${subnetBase}.${i}`)
    }

    for (let i = 0; i < ips.length; i += BATCH_SIZE) {
      const batch = ips.slice(i, i + BATCH_SIZE)
      await Promise.all(
        batch.map(async (ip) => {
          const url = `http://${ip}`
          try {
            const response = await fetch(`${url}/system/info`, {
              signal: AbortSignal.timeout(1500),
              targetAddressSpace: 'local',
            })
            const json = await response.json()
            if (json.data) {
              set((state) => ({
                discoveredDevices: [
                  ...state.discoveredDevices,
                  { ip, url, version: json.data },
                ],
              }))
            }
          } catch {
            // Host unreachable, ignore
          } finally {
            set((state) => ({ scanProgress: state.scanProgress + 1 }))
          }
        })
      )
    }

    set({ isScanning: false })
  },
}))

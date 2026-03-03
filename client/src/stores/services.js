import { create } from 'zustand'
import { servicesApi } from '@/api/services'
import { useConnectionStore } from './connection'

const POLL_INTERVAL = 1000
const POLL_TIMEOUT = 10000

function pollServiceState(apiClient, name, predicate) {
  return new Promise((resolve) => {
    const start = Date.now()

    const poll = async () => {
      try {
        const service = await servicesApi.getService(apiClient, name)
        useServicesStore.setState((state) => ({
          services: state.services.map((s) => (s.name === name ? service : s)),
        }))
        if (predicate(service)) {
          resolve(true)
          return
        }
      } catch {
        // Polling failure - continue trying
      }

      if (Date.now() - start >= POLL_TIMEOUT) {
        resolve(false)
        return
      }

      setTimeout(poll, POLL_INTERVAL)
    }

    setTimeout(poll, POLL_INTERVAL)
  })
}

async function executeServiceAction(set, get, name, apiCall, predicate) {
  const { apiClient } = useConnectionStore.getState()
  set((state) => ({
    actionsInProgress: { ...state.actionsInProgress, [name]: true },
  }))

  try {
    await apiCall(apiClient, name)
    const reached = await pollServiceState(apiClient, name, predicate)
    if (!reached) {
      await get().fetchServices()
    }
  } finally {
    set((state) => {
      const next = { ...state.actionsInProgress }
      delete next[name]
      return { actionsInProgress: next }
    })
  }
}

export const useServicesStore = create((set, get) => ({
  services: [],
  loading: false,
  error: null,
  actionsInProgress: {},
  logContent: null,
  logServiceName: null,
  logLoading: false,

  fetchServices: async () => {
    const { apiClient } = useConnectionStore.getState()
    if (!apiClient) {
      return
    }
    set({ loading: true })
    try {
      const services = await servicesApi.getServices(apiClient)
      set({ services, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  startService: (name) =>
    executeServiceAction(set, get, name, servicesApi.startService, (s) => s.state === 'active'),

  stopService: (name) =>
    executeServiceAction(set, get, name, servicesApi.stopService, (s) => s.state === 'inactive'),

  restartService: (name) =>
    executeServiceAction(set, get, name, servicesApi.restartService, (s) => s.state === 'active'),

  fetchLog: async (name) => {
    const { apiClient } = useConnectionStore.getState()
    set({ logLoading: true, logServiceName: name, logContent: null })
    try {
      const log = await servicesApi.getServiceLog(apiClient, name)
      set({ logContent: log, logLoading: false })
    } catch {
      set({ logContent: null, logLoading: false, logServiceName: null })
    }
  },

  clearLog: () => set({ logContent: null, logServiceName: null, logLoading: false }),

  isServiceActive: (name) => {
    const { services } = get()
    const svc = services.find((s) => s.name === name)
    return svc?.state === 'active' && svc?.result === 'success'
  },

  isServiceInactive: (name) => {
    const { services } = get()
    const svc = services.find((s) => s.name === name)
    return svc?.state === 'inactive'
  },
}))

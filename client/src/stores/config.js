import { create } from 'zustand'
import { configApi } from '@/api/config'
import { modemApi } from '@/api/modem'
import { useConnectionStore } from './connection'

export const useConfigStore = create((set, get) => ({
  config: null,
  schema: null,
  modems: null,
  loading: false,
  error: null,
  previousModel: null,

  fetchConfig: async () => {
    const { apiClient } = useConnectionStore.getState()
    if (!apiClient) {
      return
    }
    set({ loading: true, error: null })
    try {
      const [config, schema, modems] = await Promise.all([
        configApi.getConfig(apiClient),
        configApi.getSchema(apiClient),
        modemApi.getModemModels(apiClient),
      ])
      set({
        config,
        schema,
        modems,
        loading: false,
        previousModel: config?.network?.modem?.model || null,
      })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  saveConfig: async (data) => {
    const { apiClient } = useConnectionStore.getState()
    if (!apiClient) {
      return
    }
    try {
      await configApi.saveConfig(apiClient, data)
      set({ config: data })
    } catch (err) {
      set({ error: err.message })
      throw err
    }
  },

  updateConfig: (data) => set({ config: data }),

  getValidBands: (modelKey) => {
    const { modems } = get()
    return modems?.[modelKey]?.validBands || modems?.generic?.validBands || []
  },
}))

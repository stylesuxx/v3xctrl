import { create } from 'zustand'
import { cameraApi } from '@/api/camera'
import { useConnectionStore } from './connection'
import { useConfigStore } from './config'

export const useCameraStore = create((set, get) => ({
  settings: {
    brightness: 0,
    contrast: 1.0,
    saturation: 1.0,
    sharpness: 0,
    'lens-position': 0,
    'analogue-gain': 1,
    'exposure-time': 32000,
  },

  initFromConfig: (config) => {
    if (!config?.camera) {
      return
    }
    const cam = config.camera
    set({
      settings: {
        brightness: cam.brightness ?? 0,
        contrast: cam.contrast ?? 1.0,
        saturation: cam.saturation ?? 1.0,
        sharpness: cam.sharpness ?? 0,
        'lens-position': cam.lensPosition ?? 0,
        'analogue-gain': cam.analogueGain ?? 1,
        'exposure-time': cam.exposureTime ?? 32000,
      },
    })
  },

  updateSetting: (name, value) => {
    set((state) => ({
      settings: { ...state.settings, [name]: value },
    }))
  },

  applySetting: async (name) => {
    const { apiClient } = useConnectionStore.getState()
    const value = get().settings[name]
    await cameraApi.setSetting(apiClient, name, value)
  },

  applySettingWithValue: async (name, value) => {
    set((state) => ({
      settings: { ...state.settings, [name]: value },
    }))
    const { apiClient } = useConnectionStore.getState()
    await cameraApi.setSetting(apiClient, name, value)
  },

  saveAllSettings: async () => {
    const { settings } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)
    config.camera.brightness = settings.brightness
    config.camera.contrast = settings.contrast
    config.camera.saturation = settings.saturation
    config.camera.sharpness = settings.sharpness
    config.camera.lensPosition = settings['lens-position']
    config.camera.analogueGain = settings['analogue-gain']
    config.camera.exposureTime = settings['exposure-time']
    await configStore.saveConfig(config)
  },
}))

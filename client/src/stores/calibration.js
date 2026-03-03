import { create } from 'zustand'
import { gpioApi } from '@/api/gpio'
import { useConnectionStore } from './connection'
import { useConfigStore } from './config'

export const useCalibrationStore = create((set, get) => ({
  steering: { min: 0, max: 0, trim: 0 },
  throttle: { min: 0, max: 0, idle: 0 },

  initFromConfig: (config) => {
    if (!config?.control) {
      return
    }
    set({
      steering: {
        min: config.control.steering?.min ?? 0,
        max: config.control.steering?.max ?? 0,
        trim: config.control.steering?.trim ?? 0,
      },
      throttle: {
        min: config.control.throttle?.min ?? 0,
        max: config.control.throttle?.max ?? 0,
        idle: config.control.throttle?.idle ?? 0,
      },
    })
  },

  setSteeringField: (field, value) => {
    set((state) => ({
      steering: { ...state.steering, [field]: value },
    }))
  },

  setThrottleField: (field, value) => {
    set((state) => ({
      throttle: { ...state.throttle, [field]: value },
    }))
  },

  sendSteeringPwm: async (field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channel = config.control.pwm.steering
    const { steering } = get()
    let value = steering[field]

    if (field === 'trim') {
      const base = steering.min + (steering.max - steering.min) / 2
      value = base + steering.trim
    }

    await gpioApi.setPwm(apiClient, channel, value)
  },

  sendThrottlePwm: async (field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channel = config.control.pwm.throttle
    const { throttle } = get()
    const value = throttle[field]

    await gpioApi.setPwm(apiClient, channel, value)
  },

  saveSteeringCalibration: async () => {
    const { steering } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)
    config.control.steering.min = steering.min
    config.control.steering.max = steering.max
    config.control.steering.trim = steering.trim
    await configStore.saveConfig(config)
  },

  saveThrottleCalibration: async () => {
    const { throttle } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)
    config.control.throttle.min = throttle.min
    config.control.throttle.max = throttle.max
    config.control.throttle.idle = throttle.idle
    await configStore.saveConfig(config)
  },
}))

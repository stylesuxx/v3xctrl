import { create } from 'zustand'
import { gpioApi } from '@/api/gpio'
import { useConnectionStore } from './connection'
import { useConfigStore } from './config'

export const useCalibrationStore = create((set, get) => ({
  mixerType: 'ackermann',
  reversible: false,
  ackermann: {
    throttle: { min: 0, max: 0, idle: 0 },
    steering: { min: 0, max: 0, trim: 0 },
  },
  differential: {
    motor: { min: 0, max: 0, idle: 0 },
    mixing: { balance: 0 },
  },
  steering: { min: 0, max: 0, trim: 0 },
  throttle: { min: 0, max: 0, idle: 0 },

  initFromConfig: (config) => {
    if (!config?.control?.mixer) {
      return
    }

    const mixerType = config.control.mixer?.type ?? 'ackermann'
    const ackermannConfig = config.control.mixer?.ackermann ?? {}
    const differentialConfig = config.control.mixer?.differential ?? {}
    const reversible = config.control.mixer?.differential?.motor?.reversible ?? false

    const ackermannThrottle = ackermannConfig.throttle ?? {}
    const ackermannSteering = ackermannConfig.steering ?? {}
    const differentialMotor = differentialConfig.motor ?? {}
    const differentialMixing = differentialConfig.mixing ?? {}

    set({
      mixerType,
      reversible,
      ackermann: {
        throttle: {
          min: ackermannThrottle.min ?? 0,
          max: ackermannThrottle.max ?? 0,
          idle: ackermannThrottle.idle ?? 0,
        },
        steering: {
          min: ackermannSteering.min ?? 0,
          max: ackermannSteering.max ?? 0,
          trim: ackermannSteering.trim ?? 0,
        },
      },
      differential: {
        motor: {
          min: differentialMotor.min ?? 0,
          max: differentialMotor.max ?? 0,
          idle: differentialMotor.idle ?? 0,
        },
        mixing: {
          balance: differentialMixing.balance ?? 0,
        },
      },
      steering: {
        min: ackermannSteering.min ?? 0,
        max: ackermannSteering.max ?? 0,
        trim: ackermannSteering.trim ?? 0,
      },
      throttle: {
        min: ackermannThrottle.min ?? 0,
        max: ackermannThrottle.max ?? 0,
        idle: ackermannThrottle.idle ?? 0,
      },
    })
  },

  setSteeringField: (field, value) => {
    set((state) => ({
      steering: { ...state.steering, [field]: value },
      ackermann: {
        ...state.ackermann,
        steering: { ...state.ackermann.steering, [field]: value },
      },
    }))
  },

  setThrottleField: (field, value) => {
    set((state) => ({
      throttle: { ...state.throttle, [field]: value },
      ackermann: {
        ...state.ackermann,
        throttle: { ...state.ackermann.throttle, [field]: value },
      },
      differential: {
        ...state.differential,
        motor: { ...state.differential.motor, [field]: value },
      },
    }))
  },

  sendSteeringPwm: async (field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channel = config.control.pwm.channelB
    const { steering } = get()
    let value = steering[field]

    if (field === 'trim') {
      const base = steering.min + (steering.max - steering.min) / 2
      value = base + steering.trim
    }

    await gpioApi.setPwm(apiClient, channel, value)
  },

  sendMotorPwm: async (channelKey, field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channel = channelKey === 'throttle' ? config.control.pwm.channelA : config.control.pwm.channelB
    const { throttle } = get()
    const value = throttle[field]

    await gpioApi.setPwm(apiClient, channel, value)
  },

  sendThrottlePwm: async (field) => {
    await get().sendMotorPwm('throttle', field)
  },

  sendBalancePwm: async () => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const { throttle, differential } = get()

    await gpioApi.setPwm(apiClient, config.control.pwm.channelA, throttle.idle + differential.mixing.balance)
    await gpioApi.setPwm(apiClient, config.control.pwm.channelB, throttle.idle - differential.mixing.balance)
  },

  saveSteeringCalibration: async () => {
    const { ackermann } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)
    config.control.mixer.ackermann.steering.min = ackermann.steering.min
    config.control.mixer.ackermann.steering.max = ackermann.steering.max
    config.control.mixer.ackermann.steering.trim = ackermann.steering.trim
    await configStore.saveConfig(config)
  },

  saveThrottleCalibration: async () => {
    const { throttle, mixerType } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)

    if (mixerType === 'ackermann') {
      config.control.mixer.ackermann.throttle.min = throttle.min
      config.control.mixer.ackermann.throttle.max = throttle.max
      config.control.mixer.ackermann.throttle.idle = throttle.idle
    } else {
      config.control.mixer.differential.motor.min = throttle.min
      config.control.mixer.differential.motor.max = throttle.max
      config.control.mixer.differential.motor.idle = throttle.idle
    }

    await configStore.saveConfig(config)
  },

  saveBalanceCalibration: async () => {
    const { differential } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)
    config.control.mixer.differential.mixing.balance = differential.mixing.balance
    await configStore.saveConfig(config)
  },
}))

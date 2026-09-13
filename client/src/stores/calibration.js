import { create } from 'zustand'
import { gpioApi } from '@/api/gpio'
import { MixerType } from '@/lib/mixer'
import { useConnectionStore } from './connection'
import { useConfigStore } from './config'

const recordLastSent = (set, channelKey, base, deadzone = null) => {
  set((state) => ({
    lastSent: { ...state.lastSent, [channelKey]: { base, deadzone } },
  }))
}

export const useCalibrationStore = create((set, get) => ({
  mixerType: MixerType.ACKERMANN,
  reversible: false,
  lastSent: { channelA: null, channelB: null },
  ackermann: {
    throttle: { min: 0, max: 0, idle: 0 },
    steering: { min: 0, max: 0, trim: 0 },
  },
  differential: {
    motor: { min: 0, max: 0, idle: 0 },
    motorA: { minForward: 0, minReverse: 0 },
    motorB: { minForward: 0, minReverse: 0 },
    mixing: { balance: 0 },
  },

  initFromConfig: (config) => {
    if (!config?.control?.mixer) {
      return
    }

    const mixerType = config.control.mixerType ?? MixerType.ACKERMANN
    const ackermannConfig = config.control.mixer?.ackermann ?? {}
    const differentialConfig = config.control.mixer?.differential ?? {}
    const reversible = differentialConfig.motor?.reversible ?? false

    const ackermannThrottle = ackermannConfig.throttle ?? {}
    const ackermannSteering = ackermannConfig.steering ?? {}
    const differentialMotor = differentialConfig.motor ?? {}
    const differentialMotorA = differentialConfig.motorA ?? {}
    const differentialMotorB = differentialConfig.motorB ?? {}
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
        motorA: {
          minForward: differentialMotorA.minForward ?? 0,
          minReverse: differentialMotorA.minReverse ?? 0,
        },
        motorB: {
          minForward: differentialMotorB.minForward ?? 0,
          minReverse: differentialMotorB.minReverse ?? 0,
        },
        mixing: {
          balance: differentialMixing.balance ?? 0,
        },
      },
    })
  },

  setAckermannSteeringField: (field, value) => {
    set((state) => ({
      ackermann: {
        ...state.ackermann,
        steering: { ...state.ackermann.steering, [field]: value },
      },
    }))
  },

  setAckermannThrottleField: (field, value) => {
    set((state) => ({
      ackermann: {
        ...state.ackermann,
        throttle: { ...state.ackermann.throttle, [field]: value },
      },
    }))
  },

  setDifferentialMotorField: (field, value) => {
    set((state) => ({
      differential: {
        ...state.differential,
        motor: { ...state.differential.motor, [field]: value },
      },
    }))
  },

  setDifferentialDeadzoneField: (motorKey, field, value) => {
    set((state) => ({
      differential: {
        ...state.differential,
        [motorKey]: { ...state.differential[motorKey], [field]: value },
      },
    }))
  },

  setDifferentialBalance: (value) => {
    set((state) => ({
      differential: {
        ...state.differential,
        mixing: { ...state.differential.mixing, balance: value },
      },
    }))
  },

  sendSteeringPwm: async (field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channel = config.control.pwm.channelB
    const { steering } = get().ackermann
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
    const channel = config.control.pwm.channelA
    const value = get().ackermann.throttle[field]

    await gpioApi.setPwm(apiClient, channel, value)
  },

  sendMotorPwm: async (channelKey, field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channel = channelKey === 'channelA' ? config.control.pwm.channelA : config.control.pwm.channelB
    const value = get().differential.motor[field]

    await gpioApi.setPwm(apiClient, channel, value)
    recordLastSent(set, channelKey, value)
  },

  sendDeadzonePwm: async (motorKey, field) => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const channelKey = motorKey === 'motorA' ? 'channelA' : 'channelB'
    const channel = config.control.pwm[channelKey]
    const { motor } = get().differential
    const deadzone = get().differential[motorKey][field]
    const signedDeadzone = field === 'minForward' ? deadzone : -deadzone
    const value = motor.idle + signedDeadzone

    await gpioApi.setPwm(apiClient, channel, value)
    recordLastSent(set, channelKey, motor.idle, signedDeadzone)
  },

  sendBalancePwm: async () => {
    const { apiClient } = useConnectionStore.getState()
    const config = useConfigStore.getState().config
    const { differential } = get()
    const valueA = differential.motor.idle + differential.mixing.balance
    const valueB = differential.motor.idle - differential.mixing.balance

    await gpioApi.setPwm(apiClient, config.control.pwm.channelA, valueA)
    recordLastSent(set, 'channelA', valueA)

    await gpioApi.setPwm(apiClient, config.control.pwm.channelB, valueB)
    recordLastSent(set, 'channelB', valueB)
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
    const { mixerType, ackermann, differential } = get()
    const configStore = useConfigStore.getState()
    const config = structuredClone(configStore.config)

    if (mixerType === MixerType.ACKERMANN) {
      config.control.mixer.ackermann.throttle.min = ackermann.throttle.min
      config.control.mixer.ackermann.throttle.max = ackermann.throttle.max
      config.control.mixer.ackermann.throttle.idle = ackermann.throttle.idle
    } else {
      config.control.mixer.differential.motor.min = differential.motor.min
      config.control.mixer.differential.motor.max = differential.motor.max
      config.control.mixer.differential.motor.idle = differential.motor.idle
      config.control.mixer.differential.motorA.minForward = differential.motorA.minForward
      config.control.mixer.differential.motorA.minReverse = differential.motorA.minReverse
      config.control.mixer.differential.motorB.minForward = differential.motorB.minForward
      config.control.mixer.differential.motorB.minReverse = differential.motorB.minReverse
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

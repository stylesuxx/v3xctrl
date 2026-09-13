import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCalibrationStore } from '@/stores/calibration'
import { useConnectionStore } from '@/stores/connection'
import { useConfigStore } from '@/stores/config'
import { mockConfig } from '../mocks/data'

describe('useCalibrationStore', () => {
  beforeEach(() => {
    useCalibrationStore.setState({
      mixerType: 'ackermann',
      reversible: false,
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
    })
  })

  it('initializes from config', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    initFromConfig(mockConfig)

    const state = useCalibrationStore.getState()
    expect(state.mixerType).toBe('ackermann')
    expect(state.reversible).toBe(false)
    expect(state.ackermann.steering.min).toBe(1000)
    expect(state.ackermann.steering.max).toBe(2000)
    expect(state.ackermann.throttle.min).toBe(1000)
    expect(state.ackermann.throttle.max).toBe(2000)
    expect(state.ackermann.throttle.idle).toBe(1500)
  })

  it('initializes mixer fields from a differential config', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    const differentialConfig = {
      ...mockConfig,
      control: {
        ...mockConfig.control,
        mixerType: 'differential',
        mixer: {
          differential: {
            motor: { reversible: true, min: 900, max: 2100, idle: 1500 },
            mixing: { scale: 100, invert: false, expo: 0, balance: 15 },
          },
        },
      },
    }
    initFromConfig(differentialConfig)

    const state = useCalibrationStore.getState()
    expect(state.mixerType).toBe('differential')
    expect(state.reversible).toBe(true)
    expect(state.differential.motor.min).toBe(900)
    expect(state.differential.motor.max).toBe(2100)
    expect(state.differential.motor.idle).toBe(1500)
    expect(state.differential.mixing.balance).toBe(15)
  })

  it('defaults mixer fields when config has no mixer section', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    const legacyConfig = structuredClone(mockConfig)
    delete legacyConfig.control.mixer
    initFromConfig(legacyConfig)

    const state = useCalibrationStore.getState()
    expect(state.mixerType).toBe('ackermann')
    expect(state.reversible).toBe(false)
  })

  it('updates ackermann steering fields', () => {
    const { setAckermannSteeringField } = useCalibrationStore.getState()
    setAckermannSteeringField('min', 900)
    expect(useCalibrationStore.getState().ackermann.steering.min).toBe(900)
  })

  it('updates ackermann throttle fields', () => {
    const { setAckermannThrottleField } = useCalibrationStore.getState()
    setAckermannThrottleField('idle', 1550)
    expect(useCalibrationStore.getState().ackermann.throttle.idle).toBe(1550)
  })

  it('updates differential motor fields', () => {
    const { setDifferentialMotorField } = useCalibrationStore.getState()
    setDifferentialMotorField('idle', 1550)
    expect(useCalibrationStore.getState().differential.motor.idle).toBe(1550)
  })

  it('updates differential balance', () => {
    const { setDifferentialBalance } = useCalibrationStore.getState()
    setDifferentialBalance(25)
    expect(useCalibrationStore.getState().differential.mixing.balance).toBe(25)
  })

  it('calculates trim correctly when sending steering PWM', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      ackermann: {
        steering: { min: 1000, max: 2000, trim: 50 },
        throttle: { min: 1000, max: 2000, idle: 1500 },
      },
    })

    await useCalibrationStore.getState().sendSteeringPwm('trim')

    // base = 1000 + ((2000 - 1000) / 2) = 1500
    // value = 1500 + 50 = 1550
    expect(mockPwm).toHaveBeenCalledWith('/gpio/1/pwm', { value: 1550 })
  })

  it('sends raw value for non-trim steering fields', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      ackermann: {
        steering: { min: 900, max: 2000, trim: 0 },
        throttle: { min: 1000, max: 2000, idle: 1500 },
      },
    })

    await useCalibrationStore.getState().sendSteeringPwm('min')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/1/pwm', { value: 900 })
  })

  it('sends throttle PWM value', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      ackermann: {
        steering: { min: 1000, max: 2000, trim: 0 },
        throttle: { min: 1000, max: 2000, idle: 1500 },
      },
    })

    await useCalibrationStore.getState().sendThrottlePwm('idle')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/0/pwm', { value: 1500 })
  })

  it('sends motor PWM value to the requested channel', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        mixing: { balance: 0 },
      },
    })

    await useCalibrationStore.getState().sendMotorPwm('channelA', 'min')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/0/pwm', { value: 1000 })

    await useCalibrationStore.getState().sendMotorPwm('channelB', 'max')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/1/pwm', { value: 2000 })
  })

  it('updates per motor dead-zone fields independently', () => {
    const { setDifferentialDeadzoneField } = useCalibrationStore.getState()
    setDifferentialDeadzoneField('motorA', 'minForward', 40)
    setDifferentialDeadzoneField('motorB', 'minForward', 55)

    const { differential } = useCalibrationStore.getState()
    expect(differential.motorA.minForward).toBe(40)
    expect(differential.motorB.minForward).toBe(55)
  })

  it('sends dead-zone PWM as idle plus/minus the dead-zone on that motor channel', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        motorA: { minForward: 40, minReverse: 20 },
        motorB: { minForward: 60, minReverse: 30 },
        mixing: { balance: 0 },
      },
    })

    await useCalibrationStore.getState().sendDeadzonePwm('motorA', 'minForward')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/0/pwm', { value: 1540 })

    await useCalibrationStore.getState().sendDeadzonePwm('motorA', 'minReverse')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/0/pwm', { value: 1480 })

    await useCalibrationStore.getState().sendDeadzonePwm('motorB', 'minForward')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/1/pwm', { value: 1560 })

    await useCalibrationStore.getState().sendDeadzonePwm('motorB', 'minReverse')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/1/pwm', { value: 1470 })
  })

  it('records what was last sent per channel, with the dead-zone signed by direction', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})

    useConnectionStore.setState({ apiClient: { put: mockPwm } })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      lastSent: { channelA: null, channelB: null },
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        motorA: { minForward: 40, minReverse: 20 },
        motorB: { minForward: 60, minReverse: 30 },
        mixing: { balance: 0 },
      },
    })

    await useCalibrationStore.getState().sendMotorPwm('channelA', 'max')
    expect(useCalibrationStore.getState().lastSent.channelA).toEqual({ base: 2000, deadzone: null })

    await useCalibrationStore.getState().sendDeadzonePwm('motorA', 'minForward')
    expect(useCalibrationStore.getState().lastSent.channelA).toEqual({ base: 1500, deadzone: 40 })

    await useCalibrationStore.getState().sendDeadzonePwm('motorB', 'minReverse')
    expect(useCalibrationStore.getState().lastSent.channelB).toEqual({ base: 1500, deadzone: -30 })
  })

  it('leaves the last sent value untouched when the request fails', async () => {
    const mockPwm = vi.fn().mockRejectedValue(new Error('nope'))

    useConnectionStore.setState({ apiClient: { put: mockPwm } })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      lastSent: { channelA: { base: 1500, deadzone: null }, channelB: null },
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        motorA: { minForward: 40, minReverse: 20 },
        motorB: { minForward: 60, minReverse: 30 },
        mixing: { balance: 0 },
      },
    })

    // A failed send means the channel did not change either, so the old value still holds
    await expect(useCalibrationStore.getState().sendMotorPwm('channelA', 'max')).rejects.toThrow()
    expect(useCalibrationStore.getState().lastSent.channelA).toEqual({ base: 1500, deadzone: null })
  })

  it('initializes per motor dead-zones from a differential config', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    const config = {
      ...mockConfig,
      control: {
        ...mockConfig.control,
        mixerType: 'differential',
        mixer: {
          differential: {
            motor: { reversible: true, min: 1000, max: 2000, idle: 1500 },
            motorA: { minForward: 35, minReverse: 15 },
            motorB: { minForward: 50, minReverse: 25 },
            mixing: { balance: 0 },
          },
        },
      },
    }
    initFromConfig(config)

    const { differential } = useCalibrationStore.getState()
    expect(differential.motorA.minForward).toBe(35)
    expect(differential.motorA.minReverse).toBe(15)
    expect(differential.motorB.minForward).toBe(50)
    expect(differential.motorB.minReverse).toBe(25)
  })

  it('sends balance PWM as idle plus/minus balance offset to each motor channel', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        mixing: { balance: 30 },
      },
    })

    await useCalibrationStore.getState().sendBalancePwm()
    expect(mockPwm).toHaveBeenNthCalledWith(1, '/gpio/0/pwm', { value: 1530 })
    expect(mockPwm).toHaveBeenNthCalledWith(2, '/gpio/1/pwm', { value: 1470 })
  })

  it('saves steering calibration to config', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      ackermann: { throttle: { min: 1000, max: 2000, idle: 1500 }, steering: { min: 900, max: 2100, trim: 25 } },
    })

    await useCalibrationStore.getState().saveSteeringCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.mixer.ackermann.steering.min).toBe(900)
    expect(saved.control.mixer.ackermann.steering.max).toBe(2100)
    expect(saved.control.mixer.ackermann.steering.trim).toBe(25)
  })

  it('saves throttle calibration to config in ackermann mode', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      mixerType: 'ackermann',
      ackermann: { throttle: { min: 1100, max: 1900, idle: 1500 }, steering: { min: 1000, max: 2000, trim: 0 } },
    })

    await useCalibrationStore.getState().saveThrottleCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.mixer.ackermann.throttle.min).toBe(1100)
    expect(saved.control.mixer.ackermann.throttle.max).toBe(1900)
    expect(saved.control.mixer.ackermann.throttle.idle).toBe(1500)
  })

  it('saves throttle calibration to config in differential mode', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      mixerType: 'differential',
      differential: {
        motor: { min: 1100, max: 1900, idle: 1500 },
        motorA: { minForward: 30, minReverse: 20 },
        motorB: { minForward: 45, minReverse: 25 },
        mixing: { balance: 0 },
      },
    })

    await useCalibrationStore.getState().saveThrottleCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.mixer.differential.motor.min).toBe(1100)
    expect(saved.control.mixer.differential.motor.max).toBe(1900)
    expect(saved.control.mixer.differential.motor.idle).toBe(1500)
    expect(saved.control.mixer.differential.motorA.minForward).toBe(30)
    expect(saved.control.mixer.differential.motorA.minReverse).toBe(20)
    expect(saved.control.mixer.differential.motorB.minForward).toBe(45)
    expect(saved.control.mixer.differential.motorB.minReverse).toBe(25)
  })

  it('saves balance calibration to config, leaving throttle/motor ranges untouched', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      differential: { motor: { min: 1000, max: 2000, idle: 1500 }, mixing: { balance: 40 } },
    })

    await useCalibrationStore.getState().saveBalanceCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.mixer.differential.mixing.balance).toBe(40)
    expect(saved.control.mixer.differential.motor.min).toBe(mockConfig.control.mixer.differential.motor.min)
    expect(saved.control.mixer.ackermann.throttle.min).toBe(mockConfig.control.mixer.ackermann.throttle.min)
  })

  it('does not mutate original config when saving', async () => {
    const originalConfig = structuredClone(mockConfig)
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: originalConfig, saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      ackermann: { throttle: { min: 1000, max: 2000, idle: 1500 }, steering: { min: 800, max: 2200, trim: 100 } },
    })

    await useCalibrationStore.getState().saveSteeringCalibration()

    expect(originalConfig.control.mixer.ackermann.steering.min).toBe(1000)
  })

  it('ignores initFromConfig when config has no control section', () => {
    useCalibrationStore.getState().initFromConfig({})
    const state = useCalibrationStore.getState()
    expect(state.ackermann.steering.min).toBe(0)
  })
})

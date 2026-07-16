import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCalibrationStore } from '@/stores/calibration'
import { useConnectionStore } from '@/stores/connection'
import { useConfigStore } from '@/stores/config'
import { mockConfig } from '../mocks/data'

describe('useCalibrationStore', () => {
  beforeEach(() => {
    useCalibrationStore.setState({
      mixerType: 'car',
      reversible: false,
      steering: { min: 0, max: 0, trim: 0 },
      throttle: { min: 0, max: 0, idle: 0 },
    })
  })

  it('initializes from config', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    initFromConfig(mockConfig)

    const state = useCalibrationStore.getState()
    expect(state.mixerType).toBe('car')
    expect(state.reversible).toBe(false)
    expect(state.steering.min).toBe(1000)
    expect(state.steering.max).toBe(2000)
    expect(state.steering.trim).toBe(0)
    expect(state.throttle.min).toBe(1000)
    expect(state.throttle.max).toBe(2000)
    expect(state.throttle.idle).toBe(1500)
  })

  it('initializes mixer fields from a differential config', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    const differentialConfig = {
      ...mockConfig,
      control: {
        ...mockConfig.control,
        mixer: { type: 'differential', differential: { reversible: true } },
      },
    }
    initFromConfig(differentialConfig)

    const state = useCalibrationStore.getState()
    expect(state.mixerType).toBe('differential')
    expect(state.reversible).toBe(true)
  })

  it('defaults mixer fields when config has no mixer section', () => {
    const { initFromConfig } = useCalibrationStore.getState()
    const legacyConfig = structuredClone(mockConfig)
    delete legacyConfig.control.mixer
    initFromConfig(legacyConfig)

    const state = useCalibrationStore.getState()
    expect(state.mixerType).toBe('car')
    expect(state.reversible).toBe(false)
  })

  it('updates steering fields', () => {
    const { setSteeringField } = useCalibrationStore.getState()
    setSteeringField('min', 900)
    expect(useCalibrationStore.getState().steering.min).toBe(900)
  })

  it('updates throttle fields', () => {
    const { setThrottleField } = useCalibrationStore.getState()
    setThrottleField('idle', 1550)
    expect(useCalibrationStore.getState().throttle.idle).toBe(1550)
  })

  it('calculates trim correctly when sending steering PWM', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      steering: { min: 1000, max: 2000, trim: 50 },
      throttle: { min: 1000, max: 2000, idle: 1500 },
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
      steering: { min: 900, max: 2000, trim: 0 },
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
      throttle: { min: 1000, max: 2000, idle: 1500 },
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
      throttle: { min: 1000, max: 2000, idle: 1500 },
    })

    await useCalibrationStore.getState().sendMotorPwm('throttle', 'min')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/0/pwm', { value: 1000 })

    await useCalibrationStore.getState().sendMotorPwm('steering', 'max')
    expect(mockPwm).toHaveBeenCalledWith('/gpio/1/pwm', { value: 2000 })
  })

  it('sends balance PWM as idle plus/minus trim to each motor channel', async () => {
    const mockPwm = vi.fn().mockResolvedValue({})
    const mockClient = { put: mockPwm }

    useConnectionStore.setState({ apiClient: mockClient })
    useConfigStore.setState({ config: mockConfig })

    useCalibrationStore.setState({
      throttle: { min: 1000, max: 2000, idle: 1500 },
      steering: { min: 1000, max: 2000, trim: 30 },
    })

    await useCalibrationStore.getState().sendBalancePwm()
    expect(mockPwm).toHaveBeenNthCalledWith(1, '/gpio/0/pwm', { value: 1530 })
    expect(mockPwm).toHaveBeenNthCalledWith(2, '/gpio/1/pwm', { value: 1470 })
  })

  it('saves steering calibration to config', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      steering: { min: 900, max: 2100, trim: 25 },
    })

    await useCalibrationStore.getState().saveSteeringCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.steering.min).toBe(900)
    expect(saved.control.steering.max).toBe(2100)
    expect(saved.control.steering.trim).toBe(25)
  })

  it('saves throttle calibration to config', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      throttle: { min: 1100, max: 1900, idle: 1500 },
    })

    await useCalibrationStore.getState().saveThrottleCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.throttle.min).toBe(1100)
    expect(saved.control.throttle.max).toBe(1900)
    expect(saved.control.throttle.idle).toBe(1500)
  })

  it('saves balance calibration to config, leaving throttle/steering ranges untouched', async () => {
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      steering: { min: 1000, max: 2000, trim: 40 },
    })

    await useCalibrationStore.getState().saveBalanceCalibration()

    expect(mockSaveConfig).toHaveBeenCalledTimes(1)
    const saved = mockSaveConfig.mock.calls[0][0]
    expect(saved.control.steering.trim).toBe(40)
    expect(saved.control.steering.min).toBe(mockConfig.control.steering.min)
    expect(saved.control.throttle.min).toBe(mockConfig.control.throttle.min)
  })

  it('does not mutate original config when saving', async () => {
    const originalConfig = structuredClone(mockConfig)
    const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
    useConfigStore.setState({ config: originalConfig, saveConfig: mockSaveConfig })

    useCalibrationStore.setState({
      steering: { min: 800, max: 2200, trim: 100 },
    })

    await useCalibrationStore.getState().saveSteeringCalibration()

    expect(originalConfig.control.steering.min).toBe(1000)
  })

  it('ignores initFromConfig when config has no control section', () => {
    useCalibrationStore.getState().initFromConfig({})
    const state = useCalibrationStore.getState()
    expect(state.steering.min).toBe(0)
  })
})

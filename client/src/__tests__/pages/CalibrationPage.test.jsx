import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useServicesStore } from '@/stores/services'
import { useConfigStore } from '@/stores/config'
import { useCalibrationStore } from '@/stores/calibration'
import { createApiClient } from '@/api/client'
import { CalibrationPage } from '@/pages/CalibrationPage'
import { mockConfig } from '../mocks/data'

const BASE = 'http://test-device'

const inactiveControlService = [
  { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
]

describe('CalibrationPage', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
    useServicesStore.setState({
      services: [],
      loading: false,
      error: null,
      actionsInProgress: {},
    })
    useConfigStore.setState({
      config: mockConfig,
      schema: null,
      loading: false,
      error: null,
    })
    useCalibrationStore.setState({
      mixerType: 'ackermann',
      reversible: false,
      ackermann: {
        throttle: { min: 1000, max: 2000, idle: 1500 },
        steering: { min: 1000, max: 2000, trim: 0 },
      },
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        mixing: { balance: 0 },
      },
    })
  })

  it('shows service warning when control service is running', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CalibrationPage />)
    await waitFor(() => {
      expect(screen.getByText(/calibration cannot be run/i)).toBeInTheDocument()
    })
  })

  it('does not show calibration controls when service is active', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CalibrationPage />)
    expect(screen.queryByText('Steering')).not.toBeInTheDocument()
  })

  it('shows calibration controls when control service is inactive', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)
    await waitFor(() => {
      expect(screen.getByText('Steering')).toBeInTheDocument()
      expect(screen.getByText('Throttle')).toBeInTheDocument()
    })
  })

  it('renders PWM controls for steering fields', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)
    await waitFor(() => {
      expect(screen.getAllByText('Steering Min').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Steering Max').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Steering Trim').length).toBeGreaterThan(0)
    })
  })

  it('renders PWM controls for throttle fields', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)
    await waitFor(() => {
      expect(screen.getAllByText('Throttle Min (Reverse)').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Throttle Max (Forward)').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Throttle Neutral').length).toBeGreaterThan(0)
    })
  })

  it('renders save calibration buttons', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)
    await waitFor(() => {
      const saveButtons = screen.getAllByText('Save calibration')
      expect(saveButtons).toHaveLength(2)
    })
  })

  it('updates steering value when PWM input changes', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Steering Min').length).toBeGreaterThan(0)
    })

    // Find the input next to "Steering Min" label
    const inputs = screen.getAllByRole('spinbutton')
    fireEvent.change(inputs[0], { target: { value: '1100' } })

    expect(useCalibrationStore.getState().ackermann.steering.min).toBe(1100)
  })

  it('updates throttle value when PWM input changes', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Throttle Min (Reverse)').length).toBeGreaterThan(0)
    })

    // Throttle inputs are after steering inputs (3 steering + first throttle = index 3)
    const inputs = screen.getAllByRole('spinbutton')
    fireEvent.change(inputs[3], { target: { value: '900' } })

    expect(useCalibrationStore.getState().ackermann.throttle.min).toBe(900)
  })

  it('calls sendSteeringPwm when send button is clicked', async () => {
    const sendSteeringPwm = vi.fn()
    useCalibrationStore.setState({ sendSteeringPwm })
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Steering Min').length).toBeGreaterThan(0)
    })

    // Click the first "Send" button (Steering Min)
    const sendButtons = screen.getAllByText('Send')
    fireEvent.click(sendButtons[0])

    expect(sendSteeringPwm).toHaveBeenCalledWith('min')
  })

  it('calls sendThrottlePwm when send button is clicked', async () => {
    const sendThrottlePwm = vi.fn()
    useCalibrationStore.setState({ sendThrottlePwm })
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Throttle Min (Reverse)').length).toBeGreaterThan(0)
    })

    // Throttle send buttons are after steering send buttons (3 steering = first throttle at index 3)
    const sendButtons = screen.getAllByText('Send')
    fireEvent.click(sendButtons[3])

    expect(sendThrottlePwm).toHaveBeenCalledWith('min')
  })

  it('calls saveSteeringCalibration when save button is clicked', async () => {
    const saveSteeringCalibration = vi.fn()
    useCalibrationStore.setState({ saveSteeringCalibration })
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      const saveButtons = screen.getAllByText('Save calibration')
      expect(saveButtons).toHaveLength(2)
    })

    const saveButtons = screen.getAllByText('Save calibration')
    fireEvent.click(saveButtons[0])

    expect(saveSteeringCalibration).toHaveBeenCalled()
  })

  it('calls saveThrottleCalibration when save button is clicked', async () => {
    const saveThrottleCalibration = vi.fn()
    useCalibrationStore.setState({ saveThrottleCalibration })
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      const saveButtons = screen.getAllByText('Save calibration')
      expect(saveButtons).toHaveLength(2)
    })

    const saveButtons = screen.getAllByText('Save calibration')
    fireEvent.click(saveButtons[1])

    expect(saveThrottleCalibration).toHaveBeenCalled()
  })

  it('initializes calibration from config on mount', () => {
    useServicesStore.setState({ services: inactiveControlService })
    useCalibrationStore.setState({
      ackermann: {
        steering: { min: 0, max: 0, trim: 0 },
        throttle: { min: 0, max: 0, idle: 0 },
      },
    })

    render(<CalibrationPage />)

    // initFromConfig should have been called with mockConfig
    const state = useCalibrationStore.getState()
    expect(state.ackermann.steering.min).toBe(mockConfig.control.mixer.ackermann.steering.min)
    expect(state.ackermann.steering.max).toBe(mockConfig.control.mixer.ackermann.steering.max)
    expect(state.ackermann.throttle.idle).toBe(mockConfig.control.mixer.ackermann.throttle.idle)
  })

  it('renders info text for steering and throttle', async () => {
    useServicesStore.setState({ services: inactiveControlService })

    render(<CalibrationPage />)

    await waitFor(() => {
      // Steering note mentions "servo" and "trim"
      expect(screen.getByText(/servo makes clicking/i)).toBeInTheDocument()
      // Throttle note mentions "ESC"
      expect(screen.getByText(/calibrating your ESC/i)).toBeInTheDocument()
    })
  })
})

const differentialConfig = {
  ...mockConfig,
  control: {
    ...mockConfig.control,
    mixerType: 'differential',
    mixer: {
      ackermann: mockConfig.control.mixer.ackermann,
      differential: {
        motor: { min: 1000, max: 2000, failsafe: 1500, idle: 1500, scaleForward: 100, scaleReverse: 100, expo: 0, reversible: false },
        motorA: { minForward: 0, minReverse: 0 },
        motorB: { minForward: 0, minReverse: 0 },
        mixing: { scale: 100, invert: false, expo: 0, balance: 0 },
      },
    },
  },
}

describe('CalibrationPage - differential mixer', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
    useServicesStore.setState({
      services: inactiveControlService,
      loading: false,
      error: null,
      actionsInProgress: {},
    })
    useConfigStore.setState({
      config: differentialConfig,
      schema: null,
      loading: false,
      error: null,
    })
    useCalibrationStore.setState({
      mixerType: 'differential',
      reversible: false,
      lastSent: { channelA: null, channelB: null },
      ackermann: {
        throttle: { min: 1000, max: 2000, idle: 1500 },
        steering: { min: 1000, max: 2000, trim: 0 },
      },
      differential: {
        motor: { min: 1000, max: 2000, idle: 1500 },
        motorA: { minForward: 0, minReverse: 0 },
        motorB: { minForward: 0, minReverse: 0 },
        mixing: { balance: 0 },
      },
    })
  })

  it('renders Motor A/B and balance panels instead of Steering', async () => {
    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getByText('Motor A')).toBeInTheDocument()
      expect(screen.getByText('Motor B')).toBeInTheDocument()
      expect(screen.getByText('Motor balance')).toBeInTheDocument()
    })
    expect(screen.queryByText('Steering')).not.toBeInTheDocument()
  })

  it('renders shared motor fields for both panels', async () => {
    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Motor Min').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Motor Max').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Motor Idle').length).toBeGreaterThan(0)
    })
  })

  it('renders differential values, not ackermann values, in the motor panels', async () => {
    const mismatchedConfig = {
      ...differentialConfig,
      control: {
        ...differentialConfig.control,
        mixer: {
          ...differentialConfig.control.mixer,
          ackermann: {
            ...differentialConfig.control.mixer.ackermann,
            throttle: { ...differentialConfig.control.mixer.ackermann.throttle, min: 1111, max: 1999, idle: 1499 },
          },
          differential: {
            ...differentialConfig.control.mixer.differential,
            motor: { ...differentialConfig.control.mixer.differential.motor, min: 1050, max: 1950, idle: 1500 },
          },
        },
      },
    }
    useConfigStore.setState({ config: mismatchedConfig })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByDisplayValue('1050').length).toBeGreaterThan(0)
    })
    expect(screen.queryByDisplayValue('1111')).not.toBeInTheDocument()
  })

  it('calls sendMotorPwm with the right channel for each panel', async () => {
    const sendMotorPwm = vi.fn()
    useCalibrationStore.setState({ sendMotorPwm })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Motor Min').length).toBeGreaterThan(0)
    })

    // Motor A owns the first four controls (min, max, idle, forward dead-zone),
    // so Motor B's min is the fifth
    const sendButtons = screen.getAllByText('Send')
    fireEvent.click(sendButtons[0])
    expect(sendMotorPwm).toHaveBeenCalledWith('channelA', 'min')

    fireEvent.click(sendButtons[4])
    expect(sendMotorPwm).toHaveBeenCalledWith('channelB', 'min')
  })

  it('shows the last sent pulse per channel, and unknown before anything is sent', async () => {
    useCalibrationStore.setState({
      lastSent: {
        channelA: { base: 1500, deadzone: 70 },
        channelB: null,
      },
    })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Last sent')).toHaveLength(2)
    })

    expect(screen.getByText('+70 active')).toBeInTheDocument()
    expect(screen.getByText('1570 µs')).toBeInTheDocument()
    expect(screen.getByText('unknown')).toBeInTheDocument()
  })

  it('calls saveThrottleCalibration once for the shared motor profile', async () => {
    const saveThrottleCalibration = vi.fn()
    useCalibrationStore.setState({ saveThrottleCalibration })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getByText('Save motor calibration')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Save motor calibration'))
    expect(saveThrottleCalibration).toHaveBeenCalled()
  })

  it('calls sendBalancePwm and saveBalanceCalibration for the balance panel', async () => {
    const sendBalancePwm = vi.fn()
    const saveBalanceCalibration = vi.fn()
    useCalibrationStore.setState({ sendBalancePwm, saveBalanceCalibration })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Balance offset').length).toBeGreaterThan(0)
    })

    fireEvent.click(screen.getByText('Save balance'))
    expect(saveBalanceCalibration).toHaveBeenCalled()

    const sendButtons = screen.getAllByText('Send')
    fireEvent.click(sendButtons[sendButtons.length - 1])
    expect(sendBalancePwm).toHaveBeenCalled()
  })

  it('updates the balance offset value when its PWM input changes', async () => {
    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Balance offset').length).toBeGreaterThan(0)
    })

    const inputs = screen.getAllByRole('spinbutton')
    fireEvent.change(inputs[inputs.length - 1], { target: { value: '35' } })

    expect(useCalibrationStore.getState().differential.mixing.balance).toBe(35)
  })

  it('shows the non-reversible note by default', async () => {
    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText(/don't reverse/i).length).toBeGreaterThan(0)
    })
  })

  it('shows the reversible note when motors support reverse', async () => {
    useServicesStore.setState({ services: inactiveControlService })
    const reversibleDifferentialConfig = {
      ...differentialConfig,
      control: {
        ...differentialConfig.control,
        mixer: {
          ...differentialConfig.control.mixer,
          differential: {
            ...differentialConfig.control.mixer.differential,
            motor: { ...differentialConfig.control.mixer.differential.motor, reversible: true },
          },
        },
      },
    }
    useConfigStore.setState({ config: reversibleDifferentialConfig })
    useCalibrationStore.setState({ reversible: true })

    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText(/shared by both motors/i).length).toBeGreaterThan(0)
    })
    expect(screen.queryAllByText(/don't reverse/i).length).toBe(0)
  })

  it('shows a forward dead-zone per motor, and the reverse dead-zone only when reversible', async () => {
    render(<CalibrationPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Dead-zone Forward').length).toBeGreaterThan(0)
    })
    expect(screen.queryAllByText('Dead-zone Reverse').length).toBe(0)

    act(() => {
      useCalibrationStore.setState({ reversible: true })
    })

    await waitFor(() => {
      expect(screen.getAllByText('Dead-zone Reverse').length).toBeGreaterThan(0)
    })
  })
})

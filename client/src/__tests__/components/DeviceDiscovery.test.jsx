import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { DeviceDiscovery } from '@/components/discovery/DeviceDiscovery'

describe('DeviceDiscovery', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      deviceUrl: null,
      apiClient: null,
      connected: false,
      connecting: false,
      connectionError: null,
      isScanning: false,
      discoveredDevices: [],
      scanProgress: 0,
      connect: vi.fn().mockRejectedValue(new Error('unreachable')),
      scanSubnet: vi.fn(),
      getLastDevice: () => null,
    })
    localStorage.clear()
  })

  it('renders title and subtitle', () => {
    render(<DeviceDiscovery />)
    expect(screen.getByText('Connect to Streamer')).toBeInTheDocument()
    expect(screen.getByText(/scan your network/i)).toBeInTheDocument()
  })

  it('renders subnet input with default value', () => {
    render(<DeviceDiscovery />)
    const input = screen.getByPlaceholderText('e.g. 192.168.1')
    expect(input).toHaveValue('192.168.1')
  })

  it('renders scan button', () => {
    render(<DeviceDiscovery />)
    expect(screen.getByText('Scan Network')).toBeInTheDocument()
  })

  it('renders common subnet shortcuts', () => {
    render(<DeviceDiscovery />)
    expect(screen.getByText('192.168.1')).toBeInTheDocument()
    expect(screen.getByText('192.168.0')).toBeInTheDocument()
    expect(screen.getByText('10.0.0')).toBeInTheDocument()
    expect(screen.getByText('172.16.0')).toBeInTheDocument()
  })

  it('renders manual entry section', () => {
    render(<DeviceDiscovery />)
    expect(screen.getByPlaceholderText(/e.g. 192.168.1.100/i)).toBeInTheDocument()
    expect(screen.getByText('Connect')).toBeInTheDocument()
  })

  it('shows last connected device when available', () => {
    useConnectionStore.setState({
      getLastDevice: () => 'http://192.168.1.42',
    })

    render(<DeviceDiscovery />)
    expect(screen.getByText('Last connected')).toBeInTheDocument()
    expect(screen.getByText('http://192.168.1.42')).toBeInTheDocument()
  })

  it('shows connection error', () => {
    useConnectionStore.setState({
      connectionError: 'http://192.168.1.99',
    })

    render(<DeviceDiscovery />)
    expect(screen.getByText(/could not reach streamer/i)).toBeInTheDocument()
  })

  it('shows scanning state with progress', () => {
    useConnectionStore.setState({
      isScanning: true,
      scanProgress: 127,
    })

    render(<DeviceDiscovery />)
    expect(screen.getByText('127 / 254')).toBeInTheDocument()
    const scanningTexts = screen.getAllByText('Scanning...')
    expect(scanningTexts.length).toBeGreaterThanOrEqual(1)
  })

  it('shows discovered devices', () => {
    useConnectionStore.setState({
      discoveredDevices: [
        { ip: '192.168.1.42', url: 'http://192.168.1.42', version: { hostname: 'my-streamer' } },
      ],
    })

    render(<DeviceDiscovery />)
    expect(screen.getByText(/found 1 streamer/i)).toBeInTheDocument()
    expect(screen.getByText('my-streamer')).toBeInTheDocument()
    expect(screen.getByText('192.168.1.42')).toBeInTheDocument()
  })

  it('shows IP as fallback when discovered device has no hostname', () => {
    useConnectionStore.setState({
      discoveredDevices: [
        { ip: '192.168.1.99', url: 'http://192.168.1.99', version: {} },
      ],
    })

    render(<DeviceDiscovery />)
    // Both the device name (fallback to IP) and the IP below it should show the IP
    const ipElements = screen.getAllByText('192.168.1.99')
    expect(ipElements.length).toBeGreaterThanOrEqual(2)
  })

  it('shows no devices message after scan completes with no results', () => {
    useConnectionStore.setState({
      isScanning: false,
      scanProgress: 254,
      discoveredDevices: [],
    })

    render(<DeviceDiscovery />)
    expect(screen.getByText('No streamers found')).toBeInTheDocument()
  })

  it('calls scanSubnet when scan button is clicked', () => {
    const scanSubnet = vi.fn()
    useConnectionStore.setState({ scanSubnet })

    render(<DeviceDiscovery />)
    fireEvent.click(screen.getByText('Scan Network'))

    expect(scanSubnet).toHaveBeenCalledWith('192.168.1')
  })

  it('updates subnet base when common subnet is clicked', () => {
    render(<DeviceDiscovery />)

    fireEvent.click(screen.getByText('10.0.0'))

    const subnetInput = screen.getByPlaceholderText('e.g. 192.168.1')
    expect(subnetInput).toHaveValue('10.0.0')
  })

  it('calls connect for manual entry', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({ connect })

    render(<DeviceDiscovery />)

    const input = screen.getByPlaceholderText(/e.g. 192.168.1.100/i)
    fireEvent.change(input, { target: { value: '192.168.1.50' } })
    fireEvent.click(screen.getByText('Connect'))

    expect(connect).toHaveBeenCalledWith('http://192.168.1.50')
  })

  it('prepends http:// for manual address without protocol', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({ connect })

    render(<DeviceDiscovery />)

    const input = screen.getByPlaceholderText(/e.g. 192.168.1.100/i)
    fireEvent.change(input, { target: { value: '192.168.1.50' } })
    fireEvent.click(screen.getByText('Connect'))

    expect(connect).toHaveBeenCalledWith('http://192.168.1.50')
  })

  it('does not prepend http:// when address already has protocol', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({ connect })

    render(<DeviceDiscovery />)

    const input = screen.getByPlaceholderText(/e.g. 192.168.1.100/i)
    fireEvent.change(input, { target: { value: 'https://192.168.1.50' } })
    fireEvent.click(screen.getByText('Connect'))

    expect(connect).toHaveBeenCalledWith('https://192.168.1.50')
  })

  it('connects on Enter key in manual address input', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({ connect })

    render(<DeviceDiscovery />)

    const input = screen.getByPlaceholderText(/e.g. 192.168.1.100/i)
    fireEvent.change(input, { target: { value: '192.168.1.50' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(connect).toHaveBeenCalledWith('http://192.168.1.50')
  })

  it('does not connect on Enter with empty manual address', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({ connect })

    render(<DeviceDiscovery />)

    const input = screen.getByPlaceholderText(/e.g. 192.168.1.100/i)
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(connect).not.toHaveBeenCalled()
  })

  it('disables inputs during scanning', () => {
    useConnectionStore.setState({ isScanning: true })

    render(<DeviceDiscovery />)

    const subnetInput = screen.getByPlaceholderText('e.g. 192.168.1')
    expect(subnetInput).toBeDisabled()
  })

  it('disables inputs during connecting', () => {
    useConnectionStore.setState({ connecting: true })

    render(<DeviceDiscovery />)

    const subnetInput = screen.getByPlaceholderText('e.g. 192.168.1')
    expect(subnetInput).toBeDisabled()
    expect(screen.getByText('Connecting...')).toBeInTheDocument()
  })

  it('disables connect button when manual address is empty', () => {
    render(<DeviceDiscovery />)
    expect(screen.getByText('Connect')).toBeDisabled()
  })

  it('connects to last device when button is clicked', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({
      connect,
      getLastDevice: () => 'http://192.168.1.42',
    })

    render(<DeviceDiscovery />)
    fireEvent.click(screen.getByText('http://192.168.1.42'))

    expect(connect).toHaveBeenCalledWith('http://192.168.1.42')
  })

  it('connects to discovered device when clicked', () => {
    const connect = vi.fn().mockRejectedValue(new Error())
    useConnectionStore.setState({
      connect,
      discoveredDevices: [
        { ip: '192.168.1.42', url: 'http://192.168.1.42', version: { hostname: 'my-streamer' } },
      ],
    })

    render(<DeviceDiscovery />)
    fireEvent.click(screen.getByText('my-streamer'))

    expect(connect).toHaveBeenCalledWith('http://192.168.1.42')
  })

  it('does not scan when subnet input is empty', () => {
    const scanSubnet = vi.fn()
    useConnectionStore.setState({ scanSubnet })

    render(<DeviceDiscovery />)

    const subnetInput = screen.getByPlaceholderText('e.g. 192.168.1')
    fireEvent.change(subnetInput, { target: { value: '   ' } })
    fireEvent.click(screen.getByText('Scan Network'))

    expect(scanSubnet).not.toHaveBeenCalled()
  })
})

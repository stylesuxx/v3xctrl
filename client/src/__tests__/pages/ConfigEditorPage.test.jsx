import { describe, it, expect, beforeEach, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import '@/lib/i18n'

// Mock ResizeObserver for radix-ui components used by rjsf/shadcn
beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})
import { useConnectionStore } from '@/stores/connection'
import { useConfigStore } from '@/stores/config'
import { useServicesStore } from '@/stores/services'
import { createApiClient } from '@/api/client'
import { ConfigEditorPage } from '@/pages/ConfigEditorPage'
import { mockConfig, mockSchema } from '../mocks/data'

const BASE = 'http://test-device'

// Schema with video and control sections for testing tab switching and restart variants
const fullSchema = {
  ...mockSchema,
  properties: {
    ...mockSchema.properties,
    video: {
      propertyOrder: 20,
      type: 'object',
      title: 'Video',
      properties: {
        testSource: {
          propertyOrder: 10,
          type: 'boolean',
          title: 'Test Source',
        },
      },
    },
    camera: {
      propertyOrder: 25,
      type: 'object',
      title: 'Camera',
      properties: {
        enableHdr: {
          propertyOrder: 10,
          type: 'boolean',
          title: 'Enable HDR',
        },
      },
    },
    control: {
      propertyOrder: 30,
      type: 'object',
      title: 'Control',
      properties: {
        autostart: {
          propertyOrder: 10,
          type: 'boolean',
          title: 'Autostart',
        },
      },
    },
  },
}

// Add a text field to network schema for easy form interaction
const schemaWithTextField = structuredClone(mockSchema)
schemaWithTextField.properties.network.properties.testField = {
  propertyOrder: 99,
  type: 'string',
  title: 'Test Field',
}

function setupStores(overrides = {}) {
  useConnectionStore.setState({
    apiClient: createApiClient(BASE),
    connected: true,
  })
  useConfigStore.setState({
    config: null,
    schema: null,
    modems: {},
    loading: false,
    error: null,
    previousModel: null,
    ...overrides,
  })
  useServicesStore.setState({
    services: [],
    loading: false,
    error: null,
    actionsInProgress: {},
  })
}

describe('ConfigEditorPage', () => {
  beforeEach(() => {
    setupStores()
  })

  it('shows loading state initially', () => {
    setupStores({ loading: true })
    render(<ConfigEditorPage />)
    expect(screen.getByText(/loading configuration/i)).toBeInTheDocument()
  })

  it('shows error state with retry button', () => {
    setupStores({ config: mockConfig, schema: mockSchema, error: 'Connection failed' })
    render(<ConfigEditorPage />)
    expect(screen.getByText(/failed to load data/i)).toBeInTheDocument()
    expect(screen.getByText('Retry')).toBeInTheDocument()
  })

  it('calls fetchConfig when retry button is clicked', () => {
    const fetchConfig = vi.fn()
    setupStores({ config: mockConfig, schema: mockSchema, error: 'Connection failed', fetchConfig })
    render(<ConfigEditorPage />)

    fireEvent.click(screen.getByText('Retry'))
    expect(fetchConfig).toHaveBeenCalled()
  })

  it('renders section tabs after loading', () => {
    setupStores({ config: mockConfig, schema: mockSchema, previousModel: 'generic' })
    render(<ConfigEditorPage />)

    const networkElements = screen.getAllByText('Network')
    expect(networkElements.length).toBeGreaterThan(0)
    const devElements = screen.getAllByText('Development')
    expect(devElements.length).toBeGreaterThan(0)
  })

  it('renders save button', () => {
    setupStores({ config: mockConfig, schema: mockSchema, previousModel: 'generic' })
    render(<ConfigEditorPage />)
    expect(screen.getByText('Save')).toBeInTheDocument()
  })

  it('renders save and restart button for sections that need it', () => {
    setupStores({ config: mockConfig, schema: mockSchema, previousModel: 'generic' })
    render(<ConfigEditorPage />)
    expect(screen.getByText('Save and restart')).toBeInTheDocument()
  })

  it('save button is disabled when form is not dirty', () => {
    setupStores({ config: mockConfig, schema: mockSchema, previousModel: 'generic' })
    render(<ConfigEditorPage />)
    expect(screen.getByText('Save')).toBeDisabled()
  })

  it('renders the rjsf form for the active section', () => {
    setupStores({ config: mockConfig, schema: mockSchema, previousModel: 'generic' })
    render(<ConfigEditorPage />)
    expect(screen.getByText('Routing')).toBeInTheDocument()
  })

  it('switches section when tab is clicked and resets dirty state', () => {
    setupStores({
      config: { ...mockConfig, network: { ...mockConfig.network, testField: 'original' } },
      schema: schemaWithTextField,
      previousModel: 'generic',
    })
    render(<ConfigEditorPage />)

    // Make form dirty by changing a field
    const textInput = screen.getByLabelText('Test Field')
    fireEvent.change(textInput, { target: { value: 'changed' } })
    expect(screen.getByText('Save')).not.toBeDisabled()

    // Switch to development tab
    const devTabs = screen.getAllByText('Development')
    fireEvent.click(devTabs[devTabs.length - 1])

    // Save should be disabled (dirty reset)
    expect(screen.getByText('Save')).toBeDisabled()
  })

  it('switches section via tab click', () => {
    setupStores({
      config: mockConfig,
      schema: fullSchema,
      previousModel: 'generic',
    })
    render(<ConfigEditorPage />)

    const videoTab = screen.getByRole('button', { name: 'Video' })
    fireEvent.click(videoTab)

    expect(screen.getByText('Test Source')).toBeInTheDocument()
  })

  it('enables save button when form data changes', () => {
    setupStores({
      config: { ...mockConfig, network: { ...mockConfig.network, testField: 'original' } },
      schema: schemaWithTextField,
      previousModel: 'generic',
    })
    render(<ConfigEditorPage />)

    const textInput = screen.getByLabelText('Test Field')
    fireEvent.change(textInput, { target: { value: 'changed' } })

    expect(screen.getByText('Save')).not.toBeDisabled()
  })

  it('disables save buttons while saving', async () => {
    let resolveSave
    const savePromise = new Promise((resolve) => { resolveSave = resolve })
    const saveConfig = vi.fn(() => savePromise)

    setupStores({
      config: { ...mockConfig, network: { ...mockConfig.network, testField: 'original' } },
      schema: schemaWithTextField,
      previousModel: 'generic',
      saveConfig,
    })
    render(<ConfigEditorPage />)

    const textInput = screen.getByLabelText('Test Field')
    fireEvent.change(textInput, { target: { value: 'changed' } })

    const saveButton = screen.getByText('Save')
    const restartButton = screen.getByText('Save and restart')

    expect(saveButton).not.toBeDisabled()
    expect(restartButton).not.toBeDisabled()

    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText('Save')).toBeDisabled()
      expect(screen.getByText('Save and restart')).toBeDisabled()
    })

    resolveSave()

    await waitFor(() => {
      expect(screen.getByText('Save')).toBeDisabled()
    })
  })

  it('calls saveConfig and restartService for service-bound section', async () => {
    const saveConfig = vi.fn(() => Promise.resolve())
    const restartService = vi.fn(() => Promise.resolve())

    setupStores({
      config: { ...mockConfig, video: { ...mockConfig.video, testSource: true } },
      schema: fullSchema,
      previousModel: 'generic',
      saveConfig,
    })
    useServicesStore.setState({ restartService })

    render(<ConfigEditorPage />)

    // Switch to video tab (maps to 'v3xctrl-video' service restart)
    const videoTabs = screen.getAllByText('Video')
    fireEvent.click(videoTabs[videoTabs.length - 1])

    await waitFor(() => {
      expect(screen.getByText('Test Source')).toBeInTheDocument()
    })

    const checkbox = screen.getByRole('checkbox', { name: 'Test Source' })
    fireEvent.click(checkbox)

    const restartButton = screen.getByText('Save and restart v3xctrl-video')
    fireEvent.click(restartButton)

    await waitFor(() => {
      expect(saveConfig).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(restartService).toHaveBeenCalledWith('v3xctrl-video')
    })
  })

  it('calls saveConfig and restartService for camera section', async () => {
    const saveConfig = vi.fn(() => Promise.resolve())
    const restartService = vi.fn(() => Promise.resolve())

    setupStores({
      config: { ...mockConfig, camera: { ...mockConfig.camera } },
      schema: fullSchema,
      previousModel: 'generic',
      saveConfig,
    })
    useServicesStore.setState({ restartService })

    render(<ConfigEditorPage />)

    const cameraTab = screen.getByRole('button', { name: 'Camera' })
    fireEvent.click(cameraTab)

    await waitFor(() => {
      expect(screen.getByText('Enable HDR')).toBeInTheDocument()
    })

    const checkbox = screen.getByRole('checkbox', { name: 'Enable HDR' })
    fireEvent.click(checkbox)

    const restartButton = screen.getByText('Save and restart v3xctrl-video')
    fireEvent.click(restartButton)

    await waitFor(() => {
      expect(saveConfig).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(restartService).toHaveBeenCalledWith('v3xctrl-video')
    })
  })

  it('triggers reboot dialog for network section save+restart', async () => {
    const saveConfig = vi.fn(() => Promise.resolve())
    const rebootHandler = vi.fn()

    server.use(
      http.post(`${BASE}/system/reboot`, () => {
        rebootHandler()
        return HttpResponse.json({ data: { message: 'Rebooting...' }, error: null })
      }),
    )

    setupStores({
      config: { ...mockConfig, network: { ...mockConfig.network, testField: 'original' } },
      schema: schemaWithTextField,
      previousModel: 'generic',
      saveConfig,
    })
    render(<ConfigEditorPage />)

    const textInput = screen.getByLabelText('Test Field')
    fireEvent.change(textInput, { target: { value: 'changed' } })

    fireEvent.click(screen.getByText('Save and restart'))

    await waitFor(() => {
      expect(saveConfig).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(rebootHandler).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(screen.getByText(/rebooting/i)).toBeInTheDocument()
    })
  })

  it('does not show save+restart button for sections without restart mapping', () => {
    const schema = {
      title: 'Configuration',
      type: 'object',
      properties: {
        customSection: {
          propertyOrder: 10,
          type: 'object',
          title: 'Custom',
          properties: {
            field: { propertyOrder: 10, type: 'string', title: 'Field' },
          },
        },
      },
    }

    setupStores({
      config: { customSection: { field: 'test' } },
      schema,
      previousModel: 'generic',
    })
    render(<ConfigEditorPage />)

    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(screen.queryByText(/Save and restart/)).not.toBeInTheDocument()
  })
})
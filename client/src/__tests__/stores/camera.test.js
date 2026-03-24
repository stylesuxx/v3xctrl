import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useCameraStore } from '@/stores/camera'
import { useConnectionStore } from '@/stores/connection'
import { useConfigStore } from '@/stores/config'
import { mockConfig } from '../mocks/data'

describe('useCameraStore', () => {
  beforeEach(() => {
    useCameraStore.setState({
      settings: {
        brightness: 0,
        contrast: 1.0,
        saturation: 1.0,
        sharpness: 0,
        'lens-position': 0,
        'analogue-gain': 1,
        'exposure-time': 32000,
      },
    })
  })

  describe('initFromConfig', () => {
    it('initializes settings from config', () => {
      useCameraStore.getState().initFromConfig(mockConfig)

      const { settings } = useCameraStore.getState()
      expect(settings.brightness).toBe(0.0)
      expect(settings.contrast).toBe(1.0)
      expect(settings.saturation).toBe(1.0)
      expect(settings.sharpness).toBe(0.0)
      expect(settings['lens-position']).toBe(0)
      expect(settings['analogue-gain']).toBe(1)
      expect(settings['exposure-time']).toBe(32000)
    })

    it('does nothing if config has no camera section', () => {
      const originalSettings = { ...useCameraStore.getState().settings }
      useCameraStore.getState().initFromConfig({})
      expect(useCameraStore.getState().settings).toEqual(originalSettings)
    })

    it('does nothing if config is null', () => {
      const originalSettings = { ...useCameraStore.getState().settings }
      useCameraStore.getState().initFromConfig(null)
      expect(useCameraStore.getState().settings).toEqual(originalSettings)
    })
  })

  describe('updateSetting', () => {
    it('updates a single setting', () => {
      useCameraStore.getState().updateSetting('brightness', 0.5)
      expect(useCameraStore.getState().settings.brightness).toBe(0.5)
    })

    it('preserves other settings when updating one', () => {
      useCameraStore.getState().updateSetting('brightness', 0.5)
      expect(useCameraStore.getState().settings.contrast).toBe(1.0)
    })
  })

  describe('applySetting', () => {
    it('calls API with current setting value', async () => {
      const mockPut = vi.fn().mockResolvedValue({})
      useConnectionStore.setState({ apiClient: { put: mockPut } })

      useCameraStore.getState().updateSetting('brightness', 0.7)
      await useCameraStore.getState().applySetting('brightness')

      expect(mockPut).toHaveBeenCalledWith('/camera/settings/brightness', { value: 0.7 })
    })
  })

  describe('saveAllSettings', () => {
    it('saves all camera settings to config', async () => {
      const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
      useConfigStore.setState({ config: structuredClone(mockConfig), saveConfig: mockSaveConfig })

      useCameraStore.setState({
        settings: {
          brightness: 0.5,
          contrast: 1.5,
          saturation: 0.8,
          sharpness: 2.0,
          'lens-position': 5,
          'analogue-gain': 4,
          'exposure-time': 50000,
        },
      })

      await useCameraStore.getState().saveAllSettings()

      expect(mockSaveConfig).toHaveBeenCalledTimes(1)
      const savedConfig = mockSaveConfig.mock.calls[0][0]
      expect(savedConfig.camera.brightness).toBe(0.5)
      expect(savedConfig.camera.contrast).toBe(1.5)
      expect(savedConfig.camera.saturation).toBe(0.8)
      expect(savedConfig.camera.sharpness).toBe(2.0)
      expect(savedConfig.camera.lensPosition).toBe(5)
      expect(savedConfig.camera.analogueGain).toBe(4)
      expect(savedConfig.camera.exposureTime).toBe(50000)
    })

    it('does not mutate the original config', async () => {
      const originalConfig = structuredClone(mockConfig)
      const mockSaveConfig = vi.fn().mockResolvedValue(undefined)
      useConfigStore.setState({ config: originalConfig, saveConfig: mockSaveConfig })

      useCameraStore.getState().updateSetting('brightness', 0.9)
      await useCameraStore.getState().saveAllSettings()

      expect(originalConfig.camera.brightness).toBe(0.0)
    })
  })
})

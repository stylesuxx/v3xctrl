import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { useConfigStore } from '@/stores/config'
import { useCameraStore } from '@/stores/camera'
import { ServiceWarning } from '@/components/shared/ServiceWarning'
import { Info } from 'lucide-react'
import { toast } from 'sonner'

const CAMERA_SETTINGS = [
  { name: 'brightness', labelKey: 'camera.brightness', min: -1.0, max: 1.0, step: 0.1 },
  { name: 'contrast', labelKey: 'camera.contrast', min: 0.0, max: 2.0, step: 0.1 },
  { name: 'saturation', labelKey: 'camera.saturation', min: 0.0, max: 2.0, step: 0.1 },
  { name: 'sharpness', labelKey: 'camera.sharpness', min: 0.0, max: 10.0, step: 0.1 },
  { name: 'lens-position', labelKey: 'camera.lensPosition', min: 0, step: 0.1, noteKey: 'camera.lensNote' },
  { name: 'analogue-gain', labelKey: 'camera.analogueGain', min: 1, max: 16, step: 1, noteKey: 'camera.gainNote' },
  { name: 'exposure-time', labelKey: 'camera.exposureTime', min: 0, step: 100, noteKey: 'camera.exposureNote' },
]

export function CameraPage() {
  const { t } = useTranslation()
  const { fetchServices, isServiceActive } = useServicesStore()
  const { config } = useConfigStore()
  const { settings, initFromConfig, updateSetting, applySetting, applySettingWithValue, saveAllSettings } = useCameraStore()

  const videoActive = isServiceActive('v3xctrl-video')

  const handleSave = () => {
    toast.promise(saveAllSettings(), {
      loading: t('config.saving'),
      success: t('config.saved'),
      error: t('config.error'),
    })
  }

  useEffect(() => {
    fetchServices()
  }, [fetchServices])

  useEffect(() => {
    if (config) {
      initFromConfig(config)
    }
  }, [config, initFromConfig])

  return (
    <div className="space-y-4">
      <ServiceWarning
        message={t('camera.serviceWarning')}
        visible={!videoActive}
      />

      {videoActive && (
        <>
          <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{t('camera.note')}</p>
          </div>

          {CAMERA_SETTINGS.map((setting) => (
            <div key={setting.name} className="mb-3">
              <label className="mb-1 block text-sm font-medium sm:hidden">
                {t(setting.labelKey)}
              </label>
              <div className="flex items-center gap-2">
                <label className="hidden w-44 shrink-0 text-sm font-medium sm:block">
                  {t(setting.labelKey)}
                </label>
                <input
                  type="number"
                  min={setting.min}
                  max={setting.max}
                  step={setting.step}
                  value={settings[setting.name] ?? ''}
                  onChange={(e) => updateSetting(setting.name, e.target.value === '' ? '' : parseFloat(e.target.value) || 0)}
                  className="h-9 w-28 shrink-0 rounded-md border border-input bg-background px-3 text-sm"
                />
                <button
                  onClick={() => applySetting(setting.name)}
                  className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-secondary text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
                >
                  {t('camera.set')}
                </button>
                <button
                  type="button"
                  onClick={() => applySettingWithValue(setting.name, Math.round(((settings[setting.name] || 0) + setting.step) * 1e6) / 1e6)}
                  className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-secondary text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
                >
                  +{setting.step}
                </button>
                <button
                  type="button"
                  onClick={() => applySettingWithValue(setting.name, Math.round(((settings[setting.name] || 0) - setting.step) * 1e6) / 1e6)}
                  className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-secondary text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
                >
                  -{setting.step}
                </button>
              </div>
              {setting.noteKey && (
                <p className="mt-1 text-xs text-muted-foreground sm:ml-47">
                  {t(setting.noteKey)}
                </p>
              )}
            </div>
          ))}

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t('camera.saveSettings')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

import { useState, useMemo, useCallback, useEffect } from 'react'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'
import { useTranslation } from 'react-i18next'
import { useConfigStore } from '@/stores/config'
import { useConnectionStore } from '@/stores/connection'
import { useServicesStore } from '@/stores/services'
import { systemApi } from '@/api/system'
import { adaptSchemaForRjsf, buildUiSchema } from '@/lib/schemaUtils'
import { ReconnectDialog } from '@/components/shared/ReconnectDialog'
import { toast } from 'sonner'
import { RefreshCw } from 'lucide-react'

// Maps config sections to the service that needs restarting after changes.
// null = full system reboot, string = specific service name, undefined = save only.
const SECTION_RESTART = {
  network: null,
  video: 'v3xctrl-video',
  camera: 'v3xctrl-video',
  control: 'v3xctrl-control',
  development: null,
}

export function ConfigEditorPage() {
  const { t } = useTranslation()
  const {
    config,
    schema,
    modems,
    loading,
    error,
    previousModel,
    fetchConfig,
    saveConfig,
    updateConfig,
  } = useConfigStore()
  const { apiClient, disconnect } = useConnectionStore()
  const restartService = useServicesStore((s) => s.restartService)

  const [activeSection, setActiveSection] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [rebootOpen, setRebootOpen] = useState(false)

  useEffect(() => {
    if (!config || !schema) {
      fetchConfig()
    }
  }, [config, schema, fetchConfig])

  const sectionKeys = useMemo(() => {
    if (!schema?.properties) {
      return []
    }
    return Object.keys(schema.properties).sort(
      (a, b) => (schema.properties[a].propertyOrder ?? 0) - (schema.properties[b].propertyOrder ?? 0)
    )
  }, [schema])

  useEffect(() => {
    if (sectionKeys.length > 0 && !activeSection) {
      setActiveSection(sectionKeys[0])
    }
  }, [sectionKeys, activeSection])

  const handleTabSwitch = useCallback((key) => {
    setActiveSection(key)
    setDirty(false)
  }, [])

  const sectionSchemas = useMemo(() => {
    if (!schema?.properties) {
      return {}
    }
    const result = {}
    for (const key of sectionKeys) {
      const sectionProp = schema.properties[key]
      result[key] = {
        adapted: adaptSchemaForRjsf(sectionProp),
        uiSchema: sectionProp.type === 'object' ? buildUiSchema(sectionProp) : {},
      }
    }
    return result
  }, [schema, sectionKeys])

  const handleSectionChange = useCallback(
    (sectionKey, { formData }) => {
      if (sectionKey === 'network') {
        const currentModel = formData?.modem?.model
        if (currentModel && currentModel !== previousModel) {
          const validBands = modems[currentModel]?.validBands || modems.generic?.validBands || []
          formData = structuredClone(formData)
          formData.modem.allowedBands = validBands.slice()
          useConfigStore.setState({ previousModel: currentModel })
        }
      }
      const updated = { ...config, [sectionKey]: formData }
      updateConfig(updated)
      setDirty(true)
    },
    [config, previousModel, modems, updateConfig]
  )

  const handleSave = useCallback(() => {
    setSaving(true)
    const result = toast.promise(saveConfig(config), {
      loading: t('config.saving'),
      success: t('config.saved'),
      error: t('config.error'),
    })
    result.unwrap().then(() => setDirty(false)).catch(() => {}).finally(() => setSaving(false))
  }, [config, saveConfig, t])

  const handleSaveAndRestart = useCallback(() => {
    setSaving(true)
    const result = toast.promise(saveConfig(config), {
      loading: t('config.saving'),
      success: t('config.saved'),
      error: t('config.error'),
    })
    result.unwrap().then(async () => {
      setDirty(false)
      const service = SECTION_RESTART[activeSection]
      if (service === null) {
        // Full system reboot
        setRebootOpen(true)
        try {
          await systemApi.reboot(apiClient)
        } catch {
          // Expected - device is rebooting
        }
      } else {
        // Restart specific service
        toast.promise(restartService(service), {
          loading: t('config.restartingService', { service }),
          success: t('config.serviceRestarted', { service }),
          error: t('config.restartError', { service }),
        })
      }
    }).catch(() => {}).finally(() => setSaving(false))
  }, [config, saveConfig, activeSection, apiClient, restartService, t])

  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-red-500">{t('errors.fetchFailed')}</p>
        <button
          onClick={fetchConfig}
          className="inline-flex h-8 items-center gap-1 rounded-md bg-secondary px-3 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          <RefreshCw className="h-3 w-3" />
          {t('errors.retry')}
        </button>
      </div>
    )
  }

  if (loading || !schema || !config || !modems || sectionKeys.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('config.loading')}</p>
  }

  const section = sectionSchemas[activeSection]

  return (
    <div className="space-y-4">
      <div className="flex gap-1 overflow-x-auto border-b">
        {sectionKeys.map((key) => (
          <button
            key={key}
            onClick={() => handleTabSwitch(key)}
            className={`shrink-0 border-b-2 px-4 py-2 text-sm font-medium capitalize transition-colors ${
              activeSection === key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {schema.properties[key].title || key}
          </button>
        ))}
      </div>

      {section && (
        <div className="rjsf-form">
          <Form
            key={activeSection}
            schema={section.adapted}
            uiSchema={section.uiSchema}
            formData={config[activeSection]}
            validator={validator}
            onChange={(e) => handleSectionChange(activeSection, e)}
            onSubmit={handleSave}
            liveValidate
          >
            <div className="mt-4 flex justify-end gap-3">
              <button
                type="submit"
                disabled={!dirty || saving}
                className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {t('config.saveButton')}
              </button>
              {activeSection in SECTION_RESTART && (
                <button
                  type="button"
                  disabled={!dirty || saving}
                  onClick={handleSaveAndRestart}
                  className="inline-flex h-9 items-center rounded-md bg-destructive px-4 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
                >
                  {SECTION_RESTART[activeSection] === null
                    ? t('config.saveAndRestart')
                    : t('config.saveAndRestartService', { service: SECTION_RESTART[activeSection] })}
                </button>
              )}
            </div>
          </Form>
        </div>
      )}

      <ReconnectDialog
        open={rebootOpen}
        onReconnected={() => {
          setRebootOpen(false)
          fetchConfig()
        }}
        onFailed={() => {
          setRebootOpen(false)
          disconnect()
        }}
      />
    </div>
  )
}

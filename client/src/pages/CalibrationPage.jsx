import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { useConfigStore } from '@/stores/config'
import { useCalibrationStore } from '@/stores/calibration'
import { ServiceWarning } from '@/components/shared/ServiceWarning'
import { PwmControl } from '@/components/shared/PwmControl'
import { Info } from 'lucide-react'

export function CalibrationPage() {
  const { t } = useTranslation()
  const { fetchServices, isServiceInactive } = useServicesStore()
  const { config } = useConfigStore()
  const {
    steering,
    throttle,
    initFromConfig,
    setSteeringField,
    setThrottleField,
    sendSteeringPwm,
    sendThrottlePwm,
    saveSteeringCalibration,
    saveThrottleCalibration,
  } = useCalibrationStore()

  const controlInactive = isServiceInactive('v3xctrl-control')

  useEffect(() => {
    fetchServices()
  }, [fetchServices])

  useEffect(() => {
    if (config) {
      initFromConfig(config)
    }
  }, [config, initFromConfig])

  return (
    <div className="space-y-6">
      <ServiceWarning
        message={t('calibration.serviceWarning')}
        visible={!controlInactive}
      />

      {controlInactive && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Steering */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">{t('calibration.steeringTitle')}</h3>
            <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{t('calibration.steeringNote')}</p>
            </div>

            <PwmControl
              label={t('calibration.steeringMin')}
              value={steering.min}
              onChange={(v) => setSteeringField('min', v)}
              onSend={() => sendSteeringPwm('min')}
            />
            <PwmControl
              label={t('calibration.steeringMax')}
              value={steering.max}
              onChange={(v) => setSteeringField('max', v)}
              onSend={() => sendSteeringPwm('max')}
            />
            <PwmControl
              label={t('calibration.steeringTrim')}
              value={steering.trim}
              onChange={(v) => setSteeringField('trim', v)}
              onSend={() => sendSteeringPwm('trim')}
            />

            <div className="flex justify-end">
              <button
                onClick={saveSteeringCalibration}
                className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                {t('calibration.saveCalibration')}
              </button>
            </div>
          </div>

          {/* Throttle */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">{t('calibration.throttleTitle')}</h3>
            <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{t('calibration.throttleNote')}</p>
            </div>

            <PwmControl
              label={t('calibration.throttleMin')}
              value={throttle.min}
              onChange={(v) => setThrottleField('min', v)}
              onSend={() => sendThrottlePwm('min')}
            />
            <PwmControl
              label={t('calibration.throttleMax')}
              value={throttle.max}
              onChange={(v) => setThrottleField('max', v)}
              onSend={() => sendThrottlePwm('max')}
            />
            <PwmControl
              label={t('calibration.throttleNeutral')}
              value={throttle.idle}
              onChange={(v) => setThrottleField('idle', v)}
              onSend={() => sendThrottlePwm('idle')}
            />

            <div className="flex justify-end">
              <button
                onClick={saveThrottleCalibration}
                className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                {t('calibration.saveCalibration')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

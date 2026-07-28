import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { useConfigStore } from '@/stores/config'
import { useCalibrationStore } from '@/stores/calibration'
import { ServiceWarning } from '@/components/shared/ServiceWarning'
import { PwmControl } from '@/components/shared/PwmControl'
import { Info } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function CalibrationPage() {
  const { t } = useTranslation()
  const { fetchServices, isServiceInactive } = useServicesStore()
  const { config } = useConfigStore()
  const {
    mixerType,
    reversible,
    steering,
    throttle,
    initFromConfig,
    setSteeringField,
    setThrottleField,
    sendSteeringPwm,
    sendThrottlePwm,
    sendMotorPwm,
    sendBalancePwm,
    saveSteeringCalibration,
    saveThrottleCalibration,
    saveBalanceCalibration,
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

      {controlInactive && mixerType === 'ackermann' && (
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
              <Button onClick={saveSteeringCalibration}>
                {t('calibration.saveCalibration')}
              </Button>
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
              <Button onClick={saveThrottleCalibration}>
                {t('calibration.saveCalibration')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {controlInactive && mixerType === 'differential' && (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Motor A */}
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">{t('calibration.motorATitle')}</h3>
              <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <p>{t(reversible ? 'calibration.motorNoteReversible' : 'calibration.motorNoteNonReversible')}</p>
              </div>

              <PwmControl
                label={t('calibration.motorMin')}
                value={throttle.min}
                onChange={(v) => setThrottleField('min', v)}
                onSend={() => sendMotorPwm('throttle', 'min')}
              />
              <PwmControl
                label={t('calibration.motorMax')}
                value={throttle.max}
                onChange={(v) => setThrottleField('max', v)}
                onSend={() => sendMotorPwm('throttle', 'max')}
              />
              <PwmControl
                label={t('calibration.motorIdle')}
                value={throttle.idle}
                onChange={(v) => setThrottleField('idle', v)}
                onSend={() => sendMotorPwm('throttle', 'idle')}
              />
            </div>

            {/* Motor B */}
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">{t('calibration.motorBTitle')}</h3>
              <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <p>{t(reversible ? 'calibration.motorNoteReversible' : 'calibration.motorNoteNonReversible')}</p>
              </div>

              <PwmControl
                label={t('calibration.motorMin')}
                value={throttle.min}
                onChange={(v) => setThrottleField('min', v)}
                onSend={() => sendMotorPwm('steering', 'min')}
              />
              <PwmControl
                label={t('calibration.motorMax')}
                value={throttle.max}
                onChange={(v) => setThrottleField('max', v)}
                onSend={() => sendMotorPwm('steering', 'max')}
              />
              <PwmControl
                label={t('calibration.motorIdle')}
                value={throttle.idle}
                onChange={(v) => setThrottleField('idle', v)}
                onSend={() => sendMotorPwm('steering', 'idle')}
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button onClick={saveThrottleCalibration}>
              {t('calibration.saveMotorCalibration')}
            </Button>
          </div>

          {/* Motor balance */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">{t('calibration.balanceTitle')}</h3>
            <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{t('calibration.balanceNote')}</p>
            </div>

            <PwmControl
              label={t('calibration.balanceOffset')}
              value={steering.trim}
              onChange={(v) => setSteeringField('trim', v)}
              onSend={sendBalancePwm}
            />

            <div className="flex justify-end">
              <Button onClick={saveBalanceCalibration}>
                {t('calibration.saveBalance')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

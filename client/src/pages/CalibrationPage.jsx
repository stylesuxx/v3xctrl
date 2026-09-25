import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { useConfigStore } from '@/stores/config'
import { useCalibrationStore } from '@/stores/calibration'
import { MixerType } from '@/lib/mixer'
import { ServiceWarning } from '@/components/shared/ServiceWarning'
import { PwmControl } from '@/components/shared/PwmControl'
import { Info } from 'lucide-react'
import { Button } from '@/components/ui/button'

function LastSent({ entry, showDeadzone = false }) {
  const { t } = useTranslation()

  return (
    <div className="rounded-lg border border-border p-3 text-sm">
      <div className="mb-1 font-medium">{t('calibration.lastSentTitle')}</div>

      {(entry === null) ? (
        <p className="text-muted-foreground">{t('calibration.lastSentUnknown')}</p>
      ) : (
        <div className="space-y-0.5 text-muted-foreground">
          {showDeadzone && (
            <>
              <div className="flex justify-between gap-2">
                <span>{t('calibration.lastSentBase')}</span>
                <span className="tabular-nums">{entry.base} µs</span>
              </div>
              <div className="flex justify-between gap-2">
                <span>{t('calibration.lastSentDeadzone')}</span>
                <span className="tabular-nums">
                  {(entry.deadzone === null)
                    ? t('calibration.lastSentDeadzoneInactive')
                    : t('calibration.lastSentDeadzoneActive', {
                        value: (entry.deadzone > 0) ? `+${entry.deadzone}` : entry.deadzone,
                      })}
                </span>
              </div>
            </>
          )}
          <div className="flex justify-between gap-2 font-medium text-foreground">
            <span>{t('calibration.lastSentOutput')}</span>
            <span className="tabular-nums">{entry.base + (entry.deadzone ?? 0)} µs</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function CalibrationPage() {
  const { t } = useTranslation()
  const { fetchServices, isServiceInactive } = useServicesStore()
  const { config } = useConfigStore()
  const {
    mixerType,
    reversible,
    ackermann,
    differential,
    lastSent,
    initFromConfig,
    setAckermannSteeringField,
    setAckermannThrottleField,
    setDifferentialMotorField,
    setDifferentialDeadzoneField,
    setDifferentialBalance,
    sendSteeringPwm,
    sendThrottlePwm,
    sendMotorPwm,
    sendDeadzonePwm,
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

      {controlInactive && mixerType === MixerType.ACKERMANN && (
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
              value={ackermann.steering.min}
              onChange={(v) => setAckermannSteeringField('min', v)}
              onSend={() => sendSteeringPwm('min')}
            />
            <PwmControl
              label={t('calibration.steeringMax')}
              value={ackermann.steering.max}
              onChange={(v) => setAckermannSteeringField('max', v)}
              onSend={() => sendSteeringPwm('max')}
            />
            <PwmControl
              label={t('calibration.steeringTrim')}
              value={ackermann.steering.trim}
              onChange={(v) => setAckermannSteeringField('trim', v)}
              onSend={() => sendSteeringPwm('trim')}
            />

            <LastSent entry={lastSent.channelB} />

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
              value={ackermann.throttle.min}
              onChange={(v) => setAckermannThrottleField('min', v)}
              onSend={() => sendThrottlePwm('min')}
            />
            <PwmControl
              label={t('calibration.throttleMax')}
              value={ackermann.throttle.max}
              onChange={(v) => setAckermannThrottleField('max', v)}
              onSend={() => sendThrottlePwm('max')}
            />
            <PwmControl
              label={t('calibration.throttleNeutral')}
              value={ackermann.throttle.idle}
              onChange={(v) => setAckermannThrottleField('idle', v)}
              onSend={() => sendThrottlePwm('idle')}
            />

            <LastSent entry={lastSent.channelA} />

            <div className="flex justify-end">
              <Button onClick={saveThrottleCalibration}>
                {t('calibration.saveCalibration')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {controlInactive && mixerType === MixerType.DIFFERENTIAL && (
        <div className="space-y-6">
          <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              {t(reversible ? 'calibration.motorNoteReversible' : 'calibration.motorNoteNonReversible')}{' '}
              {t('calibration.motorNoteDeadzone')}
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Motor A */}
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">{t('calibration.motorATitle')}</h3>
              <PwmControl
                label={t('calibration.motorMin')}
                value={differential.motor.min}
                onChange={(v) => setDifferentialMotorField('min', v)}
                onSend={() => sendMotorPwm('channelA', 'min')}
              />
              <PwmControl
                label={t('calibration.motorMax')}
                value={differential.motor.max}
                onChange={(v) => setDifferentialMotorField('max', v)}
                onSend={() => sendMotorPwm('channelA', 'max')}
              />
              <PwmControl
                label={t('calibration.motorIdle')}
                value={differential.motor.idle}
                onChange={(v) => setDifferentialMotorField('idle', v)}
                onSend={() => sendMotorPwm('channelA', 'idle')}
              />
              <PwmControl
                label={t('calibration.motorDeadzoneForward')}
                value={differential.motorA.minForward}
                onChange={(v) => setDifferentialDeadzoneField('motorA', 'minForward', v)}
                onSend={() => sendDeadzonePwm('motorA', 'minForward')}
              />
              {reversible && (
                <PwmControl
                  label={t('calibration.motorDeadzoneReverse')}
                  value={differential.motorA.minReverse}
                  onChange={(v) => setDifferentialDeadzoneField('motorA', 'minReverse', v)}
                  onSend={() => sendDeadzonePwm('motorA', 'minReverse')}
                />
              )}

              <LastSent entry={lastSent.channelA} showDeadzone />
            </div>

            {/* Motor B */}
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">{t('calibration.motorBTitle')}</h3>
              <PwmControl
                label={t('calibration.motorMin')}
                value={differential.motor.min}
                onChange={(v) => setDifferentialMotorField('min', v)}
                onSend={() => sendMotorPwm('channelB', 'min')}
              />
              <PwmControl
                label={t('calibration.motorMax')}
                value={differential.motor.max}
                onChange={(v) => setDifferentialMotorField('max', v)}
                onSend={() => sendMotorPwm('channelB', 'max')}
              />
              <PwmControl
                label={t('calibration.motorIdle')}
                value={differential.motor.idle}
                onChange={(v) => setDifferentialMotorField('idle', v)}
                onSend={() => sendMotorPwm('channelB', 'idle')}
              />
              <PwmControl
                label={t('calibration.motorDeadzoneForward')}
                value={differential.motorB.minForward}
                onChange={(v) => setDifferentialDeadzoneField('motorB', 'minForward', v)}
                onSend={() => sendDeadzonePwm('motorB', 'minForward')}
              />
              {reversible && (
                <PwmControl
                  label={t('calibration.motorDeadzoneReverse')}
                  value={differential.motorB.minReverse}
                  onChange={(v) => setDifferentialDeadzoneField('motorB', 'minReverse', v)}
                  onSend={() => sendDeadzonePwm('motorB', 'minReverse')}
                />
              )}

              <LastSent entry={lastSent.channelB} showDeadzone />
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
              value={differential.mixing.balance}
              onChange={(v) => setDifferentialBalance(v)}
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

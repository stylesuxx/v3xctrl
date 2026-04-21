import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { useConnectionStore } from '@/stores/connection'
import { modemApi } from '@/api/modem'
import { ServiceWarning } from '@/components/shared/ServiceWarning'
import { Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ModemPage() {
  const { t } = useTranslation()
  const { fetchServices, isServiceInactive } = useServicesStore()
  const { apiClient } = useConnectionStore()
  const [modemInfo, setModemInfo] = useState(null)
  const [modemError, setModemError] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [resetting, setResetting] = useState(false)

  const controlInactive = isServiceInactive('v3xctrl-control')

  useEffect(() => {
    fetchServices()
  }, [fetchServices])

  const fetchModemInfo = useCallback(async () => {
    if (!apiClient) {
      return
    }
    setModemError(false)
    setFetching(true)
    try {
      const info = await modemApi.getModemInfo(apiClient)
      setModemInfo(info)
    } catch {
      setModemError(true)
    } finally {
      setFetching(false)
    }
  }, [apiClient])

  useEffect(() => {
    if (controlInactive && apiClient) {
      fetchModemInfo()
    }
  }, [controlInactive, apiClient, fetchModemInfo])

  const handleReset = useCallback(async () => {
    setResetting(true)
    try {
      await modemApi.resetModem(apiClient)
      const info = await modemApi.getModemInfo(apiClient)
      setModemInfo(info)
    } catch (err) {
      console.error(err)
    } finally {
      setResetting(false)
    }
  }, [apiClient])

  return (
    <div className="space-y-4">
      <ServiceWarning
        message={t('modem.serviceWarning')}
        visible={!controlInactive}
      />

      {controlInactive && (
        <>
          <div className="flex items-center justify-between">
            <Button onClick={handleReset} disabled={resetting || fetching}>
              {resetting ? t('modem.resetting') : t('modem.reset')}
            </Button>
            <Button variant="secondary" onClick={fetchModemInfo} disabled={fetching || resetting}>
              <RefreshCw className={`h-3 w-3 ${fetching ? 'animate-spin' : ''}`} />
              {modemInfo ? t('modem.refresh') : t('errors.retry')}
            </Button>
          </div>

          {modemError ? (
            <p className="text-sm text-red-500">{t('errors.fetchFailed')}</p>
          ) : !modemInfo ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('modem.fetchingSlow')}
            </div>
          ) : (
            <div className="rounded-lg border">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b">
                    <td className="px-4 py-2 font-medium">{t('modem.fields.version')}</td>
                    <td className="px-4 py-2">{modemInfo.version}</td>
                  </tr>
                  <tr className="border-b">
                    <td className="px-4 py-2 font-medium">{t('modem.fields.simStatus')}</td>
                    <td className="px-4 py-2">{modemInfo.status}</td>
                  </tr>
                  <tr className="border-b">
                    <td className="px-4 py-2 font-medium">{t('modem.fields.allowedBands')}</td>
                    <td className="px-4 py-2">{modemInfo.allowedBands?.join(', ')}</td>
                  </tr>
                  <tr className="border-b">
                    <td className="px-4 py-2 font-medium">{t('modem.fields.activeBand')}</td>
                    <td className="px-4 py-2">{modemInfo.activeBand}</td>
                  </tr>
                  <tr className="border-b">
                    <td className="px-4 py-2 font-medium">{t('modem.fields.carrier')}</td>
                    <td className="px-4 py-2">{modemInfo.carrier}</td>
                  </tr>
                  {modemInfo.contexts?.map((ctx) => (
                    <tr key={`ctx-${ctx.id}`} className="border-b">
                      <td className="px-4 py-2 font-medium">
                        {t('modem.fields.context', { id: ctx.id })}
                      </td>
                      <td className="px-4 py-2">
                        {ctx.type}: {ctx.value} ({ctx.apn})
                      </td>
                    </tr>
                  ))}
                  {modemInfo.addresses?.map((addr) => (
                    <tr key={`addr-${addr.id}`} className="border-b last:border-0">
                      <td className="px-4 py-2 font-medium">
                        {t('modem.fields.address', { id: addr.id })}
                      </td>
                      <td className="px-4 py-2">{addr.ip}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

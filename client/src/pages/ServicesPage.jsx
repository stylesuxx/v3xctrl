import { useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { Loader2, RefreshCw, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

function getServiceStatus(service) {
  switch (service.type) {
    case 'oneshot': {
      if (service.result === 'success' && ['active', 'activating'].includes(service.state)) {
        return {
          label: service.state === 'activating' ? 'running' : 'ran',
          success: true,
        }
      }
      return { label: 'failed', success: false }
    }

    case 'forking': {
      if (service.result === 'success' && service.state === 'active') {
        return { label: 'active', success: true }
      }
      return { label: 'failed', success: false }
    }

    case 'simple':
    default: { // eslint-disable-line padding-line-between-statements
      if (service.result === 'success' && service.state === 'active') {
        return { label: 'active', success: true }
      }
      return { label: 'inactive', success: false }
    }
  }
}

const ACTION_BTN = 'w-20 text-xs'
const LOG_BTN = 'w-20 text-xs'

export function ServicesPage() {
  const { t } = useTranslation()
  const {
    services,
    loading,
    error,
    actionsInProgress,
    fetchServices,
    startService,
    stopService,
    restartService,
    fetchLog,
    clearLog,
    logContent,
    logServiceName,
    logLoading,
  } = useServicesStore()

  const logOpen = logLoading || logContent

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Escape' && logOpen) {
        clearLog()
      }
    },
    [logOpen, clearLog],
  )

  const loadingRef = useRef(false)

  useEffect(() => {
    loadingRef.current = loading
  }, [loading])

  useEffect(() => {
    fetchServices()
    const interval = setInterval(() => {
      if (!loadingRef.current) {
        fetchServices()
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [fetchServices])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  if (error && services.length === 0) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-red-500">{t('errors.fetchFailed')}</p>
        <Button variant="secondary" size="sm" onClick={fetchServices}>
          <RefreshCw className="h-3 w-3" />
          {t('errors.retry')}
        </Button>
      </div>
    )
  }

  if (loading && services.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('services.loading')}</p>
  }

  if (services.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('services.noServices')}</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={fetchServices} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {t('services.refresh')}
        </Button>
      </div>
      <div className="rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-2 text-left font-medium">{t('services.columns.service')}</th>
              <th className="hidden px-4 py-2 text-left font-medium md:table-cell">{t('services.columns.type')}</th>
              <th className="px-4 py-2 text-left font-medium">{t('services.columns.status')}</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {services.map((service) => {
              const status = getServiceStatus(service)
              const isActionPending = !!actionsInProgress[service.name]
              return (
                <tr key={service.name} className="border-b last:border-0 align-top">
                  <td className="px-4 py-2 font-medium">{service.name}</td>
                  <td className="hidden px-4 py-2 md:table-cell">{service.type}</td>
                  <td className="px-4 py-2">
                    {isActionPending ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    ) : (
                      <span className={status.success ? 'text-green-600' : 'text-red-500'}>
                        {t(`services.status.${status.label}`)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex flex-col items-end gap-1 sm:flex-row sm:gap-2">
                      {(service.type === 'simple' || service.type === 'forking') && (
                        status.success ? (
                          <Button size="sm" className={ACTION_BTN} onClick={() => stopService(service.name)} disabled={isActionPending}>
                            {t('services.actions.stop')}
                          </Button>
                        ) : (
                          <Button size="sm" className={ACTION_BTN} onClick={() => startService(service.name)} disabled={isActionPending}>
                            {t('services.actions.start')}
                          </Button>
                        )
                      )}
                      {service.type === 'oneshot' && (
                        status.success && service.state === 'activating' ? (
                          <Button size="sm" className={ACTION_BTN} onClick={() => stopService(service.name)} disabled={isActionPending}>
                            {t('services.actions.stop')}
                          </Button>
                        ) : (
                          <Button size="sm" className={ACTION_BTN} onClick={() => restartService(service.name)} disabled={isActionPending}>
                            {t('services.actions.restart')}
                          </Button>
                        )
                      )}
                      <Button variant="secondary" size="sm" className={LOG_BTN} onClick={() => fetchLog(service.name)}>
                        {t('services.actions.showLogs')}
                      </Button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {logOpen && (
        // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
        <div
          role="dialog"
          aria-label={logServiceName}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={clearLog}
          onKeyDown={handleKeyDown}
        >
          {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
          <div
            className="flex max-h-[80vh] w-[calc(100%-1rem)] max-w-screen-lg flex-col overflow-hidden rounded-lg bg-card shadow-lg sm:w-[calc(100%-2rem)]"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
              <h2 className="text-sm font-semibold">{logServiceName}</h2>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={clearLog}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {logLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <pre className="min-h-0 flex-1 overflow-auto p-4 font-mono text-xs">{logContent}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

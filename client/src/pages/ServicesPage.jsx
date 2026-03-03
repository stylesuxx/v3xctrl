import { useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useServicesStore } from '@/stores/services'
import { Loader2, RefreshCw, X } from 'lucide-react'

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

const ACTION_BTN =
  'w-20 rounded bg-primary py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50'
const LOG_BTN =
  'w-20 rounded bg-secondary py-1 text-xs font-medium text-secondary-foreground hover:bg-secondary/80'

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
        <button
          onClick={fetchServices}
          className="inline-flex h-8 items-center gap-1 rounded-md bg-secondary px-3 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          <RefreshCw className="h-3 w-3" />
          {t('errors.retry')}
        </button>
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
        <button
          onClick={fetchServices}
          disabled={loading}
          className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {t('services.refresh')}
        </button>
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
                          <button
                            onClick={() => stopService(service.name)}
                            disabled={isActionPending}
                            className={ACTION_BTN}
                          >
                            {t('services.actions.stop')}
                          </button>
                        ) : (
                          <button
                            onClick={() => startService(service.name)}
                            disabled={isActionPending}
                            className={ACTION_BTN}
                          >
                            {t('services.actions.start')}
                          </button>
                        )
                      )}
                      {service.type === 'oneshot' && (
                        status.success && service.state === 'activating' ? (
                          <button
                            onClick={() => stopService(service.name)}
                            disabled={isActionPending}
                            className={ACTION_BTN}
                          >
                            {t('services.actions.stop')}
                          </button>
                        ) : (
                          <button
                            onClick={() => restartService(service.name)}
                            disabled={isActionPending}
                            className={ACTION_BTN}
                          >
                            {t('services.actions.restart')}
                          </button>
                        )
                      )}
                      <button
                        onClick={() => fetchLog(service.name)}
                        className={LOG_BTN}
                      >
                        {t('services.actions.showLogs')}
                      </button>
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
              <button
                onClick={clearLog}
                className="rounded-md p-1 hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
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

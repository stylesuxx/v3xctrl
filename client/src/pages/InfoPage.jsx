import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useConnectionStore } from '@/stores/connection'
import { systemApi } from '@/api/system'
import { RefreshCw } from 'lucide-react'

export function InfoPage() {
  const { t } = useTranslation()
  const { apiClient } = useConnectionStore()
  const [info, setInfo] = useState(null)
  const [error, setError] = useState(false)

  const fetchInfo = useCallback(async () => {
    if (!apiClient) {
      return
    }
    setError(false)
    try {
      const data = await systemApi.getInfo(apiClient)
      setInfo(data)
    } catch {
      setError(true)
    }
  }, [apiClient])

  useEffect(() => {
    fetchInfo()
  }, [fetchInfo])

  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-red-500">{t('errors.fetchFailed')}</p>
        <button
          onClick={fetchInfo}
          className="inline-flex h-8 items-center gap-1 rounded-md bg-secondary px-3 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          <RefreshCw className="h-3 w-3" />
          {t('errors.retry')}
        </button>
      </div>
    )
  }

  if (!info) {
    return <p className="text-sm text-muted-foreground">{t('info.fetching')}</p>
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-4">
        <p className="text-xs font-medium uppercase text-muted-foreground">
          {t('info.hostname')}
        </p>
        <p className="text-lg font-semibold">{info.hostname}</p>
      </div>

      <div className="rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-2 text-left font-medium">{t('info.columns.package')}</th>
              <th className="px-4 py-2 text-left font-medium">{t('info.columns.version')}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(info.packages || {}).map(([name, version]) => (
              <tr key={name} className="border-b last:border-0">
                <td className="px-4 py-2">{name}</td>
                <td className="px-4 py-2">{version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

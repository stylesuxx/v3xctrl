import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useConnectionStore } from '@/stores/connection'
import { systemApi } from '@/api/system'
import { RefreshCw, Download, Trash2 } from 'lucide-react'

function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  const kilobytes = bytes / 1024
  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(1)} KB`
  }
  const megabytes = kilobytes / 1024
  return `${megabytes.toFixed(1)} MB`
}

export function InfoPage() {
  const { t } = useTranslation()
  const { apiClient, deviceUrl } = useConnectionStore()
  const [info, setInfo] = useState(null)
  const [error, setError] = useState(false)
  const [archives, setArchives] = useState([])

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

  const fetchArchives = useCallback(async () => {
    if (!apiClient) {
      return
    }
    try {
      const data = await systemApi.getLogArchives(apiClient)
      setArchives(data)
    } catch {
      setArchives([])
    }
  }, [apiClient])

  const deleteArchive = useCallback(async (filename) => {
    if (!apiClient) {
      return
    }
    if (!window.confirm(t('info.confirmDelete', { name: filename }))) {
      return
    }
    try {
      await systemApi.deleteLogArchive(apiClient, filename)
      await fetchArchives()
    } catch {
      // fetch will update the list regardless
    }
  }, [apiClient, t, fetchArchives])

  useEffect(() => {
    fetchInfo()
    fetchArchives()
  }, [fetchInfo, fetchArchives])

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

      {archives.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('info.noArchives')}</p>
      ) : (
        <div className="rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium" colSpan="3">
                  {t('info.persistentLogs')}
                </th>
              </tr>
            </thead>
            <tbody>
              {archives.map((archive) => (
                <tr key={archive.name} className="border-b last:border-0">
                  <td className="px-4 py-2">{archive.name}</td>
                  <td className="px-4 py-2">{formatFileSize(archive.size)}</td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-flex gap-1">
                      <a
                        href={`${deviceUrl}/system/logs/${archive.name}`}
                        download
                        className="inline-flex h-7 items-center gap-1 rounded-md bg-secondary px-2 text-xs font-medium text-secondary-foreground hover:bg-secondary/80"
                      >
                        <Download className="h-3 w-3" />
                        {t('info.download')}
                      </a>
                      <button
                        onClick={() => deleteArchive(archive.name)}
                        className="inline-flex h-7 items-center gap-1 rounded-md bg-destructive px-2 text-xs font-medium text-destructive-foreground hover:bg-destructive/80"
                      >
                        <Trash2 className="h-3 w-3" />
                        {t('info.delete')}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

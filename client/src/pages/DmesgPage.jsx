import { useState, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useConnectionStore } from '@/stores/connection'
import { systemApi } from '@/api/system'
import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function DmesgPage() {
  const { t } = useTranslation()
  const { apiClient } = useConnectionStore()
  const [log, setLog] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchDmesg = useCallback(async () => {
    if (!apiClient) {
      return
    }
    setLoading(true)
    try {
      const data = await systemApi.getDmesg(apiClient)
      setLog(data.split('\n').reverse().join('\n'))
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [apiClient])

  useEffect(() => {
    fetchDmesg()
  }, [fetchDmesg])

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={fetchDmesg} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {t('dmesg.refresh')}
        </Button>
      </div>
      <textarea
        readOnly
        value={log}
        className="h-[600px] w-full rounded-md border bg-muted/50 p-3 font-mono text-xs"
      />
    </div>
  )
}

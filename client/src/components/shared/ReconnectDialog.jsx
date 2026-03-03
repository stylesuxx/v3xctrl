import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import { useConnectionStore } from '@/stores/connection'

const POLL_INTERVAL = 5000
const TIMEOUT = 90000
const FAILURE_DISPLAY = 3000

export function ReconnectDialog({ open, onReconnected, onFailed }) {
  const { t } = useTranslation()
  const connect = useConnectionStore((s) => s.connect)
  const deviceUrl = useConnectionStore((s) => s.deviceUrl)
  const [failed, setFailed] = useState(false)
  const urlRef = useRef(deviceUrl)
  const timerRef = useRef(null)
  const timeoutRef = useRef(null)

  useEffect(() => {
    if (deviceUrl) {
      urlRef.current = deviceUrl
    }
  }, [deviceUrl])

  useEffect(() => {
    if (!open) {
      setFailed(false)
      clearInterval(timerRef.current)
      clearTimeout(timeoutRef.current)
      return
    }

    const url = urlRef.current
    if (!url) {
      return
    }

    const poll = () => {
      connect(url, { silent: true })
        .then(() => {
          clearInterval(timerRef.current)
          clearTimeout(timeoutRef.current)
          onReconnected?.()
        })
        .catch(() => {})
    }

    timerRef.current = setInterval(poll, POLL_INTERVAL)

    timeoutRef.current = setTimeout(() => {
      clearInterval(timerRef.current)
      setFailed(true)
      setTimeout(() => onFailed?.(), FAILURE_DISPLAY)
    }, TIMEOUT)

    return () => {
      clearInterval(timerRef.current)
      clearTimeout(timeoutRef.current)
    }
  }, [open, connect, onReconnected, onFailed])

  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg bg-card p-6 text-center shadow-lg">
        {failed ? (
          <>
            <h2 className="mb-4 text-xl font-bold">{t('system.reconnectFailed')}</h2>
            <p className="text-muted-foreground">{t('system.reconnectFailedMsg')}</p>
          </>
        ) : (
          <>
            <h2 className="mb-4 text-xl font-bold">{t('system.rebooting')}</h2>
            <div className="mb-4 flex justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">{t('system.waitingForReconnect')}</p>
          </>
        )}
      </div>
    </div>
  )
}

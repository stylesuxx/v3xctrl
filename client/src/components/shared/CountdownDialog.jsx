import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'

export function CountdownDialog({
  open,
  title,
  message,
  countdownSeconds,
  onCountdownEnd,
  endTitle,
  endMessage,
}) {
  const { t } = useTranslation()
  const [secondsLeft, setSecondsLeft] = useState(countdownSeconds)
  const [done, setDone] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!open) {
      setSecondsLeft(countdownSeconds)
      setDone(false)
      return
    }

    timerRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          setDone(true)
          onCountdownEnd?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timerRef.current)
  }, [open, countdownSeconds, onCountdownEnd])

  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg bg-card p-6 text-center shadow-lg">
        <h2 className="mb-4 text-xl font-bold">
          {done ? endTitle || title : title}
        </h2>
        <p className="mb-2 font-semibold">
          {done ? endMessage || message : message}
        </p>
        {!done && secondsLeft > 0 && (
          <p className="text-muted-foreground">
            {t('system.seconds', { count: secondsLeft })}
          </p>
        )}
      </div>
    </div>
  )
}

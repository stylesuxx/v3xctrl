import { useState, useCallback, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useConnectionStore } from '@/stores/connection'
import { systemApi } from '@/api/system'
import { CountdownDialog } from '@/components/shared/CountdownDialog'
import { ReconnectDialog } from '@/components/shared/ReconnectDialog'
import { Menu, X } from 'lucide-react'

const EMBEDDED = import.meta.env.VITE_EMBEDDED === 'true'

export function Navbar({ tabs, activeTab, onTabChange }) {
  const { t } = useTranslation()
  const { apiClient, deviceUrl, deviceHostname, disconnect } = useConnectionStore()
  const [rebootOpen, setRebootOpen] = useState(false)
  const [shutdownOpen, setShutdownOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuTop, setMenuTop] = useState(0)
  const navRef = useRef(null)

  useEffect(() => {
    if (menuOpen && navRef.current) {
      setMenuTop(navRef.current.getBoundingClientRect().bottom)
    }
  }, [menuOpen])

  const handleReboot = useCallback(async () => {
    setMenuOpen(false)
    setRebootOpen(true)
    try {
      await systemApi.reboot(apiClient)
    } catch {
      // Expected - device is rebooting
    }
  }, [apiClient])

  const handleShutdown = useCallback(async () => {
    setMenuOpen(false)
    setShutdownOpen(true)
    try {
      await systemApi.shutdown(apiClient)
    } catch {
      // Expected - device is shutting down
    }
  }, [apiClient])

  const handleDisconnect = useCallback(() => {
    setMenuOpen(false)
    disconnect()
  }, [disconnect])

  const handleTabChange = (tabId) => {
    setMenuOpen(false)
    onTabChange(tabId)
  }

  return (
    <>
      <nav ref={navRef} className="relative z-40 border-b bg-card">
        <div className="container mx-auto flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <img src="/icon-round.png" alt="" className="h-7 w-7" />
                <span className="text-lg font-bold">{t('nav.brand')}</span>
              </div>
              <span className="mt-1 text-xs text-muted-foreground md:hidden">
                {deviceUrl}{deviceHostname && ` (${deviceHostname})`}
              </span>
            </div>
            <span className="hidden text-xs text-muted-foreground md:inline">
              {deviceUrl}{deviceHostname && ` (${deviceHostname})`}
            </span>
          </div>

          {/* Desktop actions */}
          <div className="hidden items-center gap-3 md:flex">
            {!EMBEDDED && (
              <button
                onClick={disconnect}
                className="mr-2 text-sm text-destructive hover:text-destructive/80"
              >
                {t('nav.disconnect')}
              </button>
            )}
            <button
              onClick={handleReboot}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t('nav.restart')}
            </button>
            <button
              onClick={handleShutdown}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t('nav.shutdown')}
            </button>
            <a
              href="https://discord.v3xctrl.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t('nav.discord')}
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="rounded-md p-2 text-muted-foreground hover:text-foreground md:hidden"
          >
            {menuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

      </nav>

      {/* Mobile menu backdrop + panel */}
      {menuOpen && (
        <>
          {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
          <div
            className="fixed inset-0 z-30 bg-black/50 md:hidden"
            onClick={() => setMenuOpen(false)}
            onKeyDown={(e) => { if (e.key === 'Escape') { setMenuOpen(false) } }}
          />
          <div
            className="fixed left-0 right-0 z-40 border-t bg-card px-4 py-2 shadow-lg md:hidden"
            style={{ top: menuTop }}
          >
            <div className="flex flex-col gap-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`py-2 text-left text-sm ${
                    activeTab === tab.id
                      ? 'font-medium text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t(tab.labelKey)}
                </button>
              ))}
              <hr className="my-1 border-border" />
              {!EMBEDDED && (
                <button
                  onClick={handleDisconnect}
                  className="py-2 text-left text-sm text-destructive hover:text-destructive/80"
                >
                  {t('nav.disconnect')}
                </button>
              )}
              <button
                onClick={handleReboot}
                className="py-2 text-left text-sm text-muted-foreground hover:text-foreground"
              >
                {t('nav.restart')}
              </button>
              <button
                onClick={handleShutdown}
                className="py-2 text-left text-sm text-muted-foreground hover:text-foreground"
              >
                {t('nav.shutdown')}
              </button>
              <a
                href="https://discord.v3xctrl.com"
                target="_blank"
                rel="noopener noreferrer"
                className="py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                {t('nav.discord')}
              </a>
            </div>
          </div>
        </>
      )}

      <ReconnectDialog
        open={rebootOpen}
        onReconnected={() => setRebootOpen(false)}
        onFailed={() => {
          setRebootOpen(false)
          disconnect()
        }}
      />

      <CountdownDialog
        open={shutdownOpen}
        title={t('system.shuttingDown')}
        message={t('system.shuttingDownMsg')}
        countdownSeconds={30}
        endTitle={t('system.shutdownComplete')}
        endMessage={t('system.safeToTurnOff')}
        onCountdownEnd={() => {}}
      />
    </>
  )
}

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Toaster } from 'sonner'
import { Loader2 } from 'lucide-react'
import { useConnectionStore } from '@/stores/connection'
import { useConfigStore } from '@/stores/config'
import { DeviceDiscovery } from '@/components/discovery/DeviceDiscovery'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

import { ConfigEditorPage } from '@/pages/ConfigEditorPage'
import { ServicesPage } from '@/pages/ServicesPage'
import { CalibrationPage } from '@/pages/CalibrationPage'
import { CameraPage } from '@/pages/CameraPage'
import { DmesgPage } from '@/pages/DmesgPage'
import { ModemPage } from '@/pages/ModemPage'
import { InfoPage } from '@/pages/InfoPage'

const TABS = [
  { id: 'editor', labelKey: 'tabs.configEditor', component: ConfigEditorPage },
  { id: 'services', labelKey: 'tabs.services', component: ServicesPage },
  { id: 'calibration', labelKey: 'tabs.calibration', component: CalibrationPage },
  { id: 'camera', labelKey: 'tabs.camera', component: CameraPage },
  { id: 'dmesg', labelKey: 'tabs.dmesg', component: DmesgPage },
  { id: 'modem', labelKey: 'tabs.modem', component: ModemPage },
  { id: 'info', labelKey: 'tabs.info', component: InfoPage },
]

function getTabFromHash() {
  const hash = window.location.hash.replace('#', '')
  return TABS.find((t) => t.id === hash)?.id || 'editor'
}

const EMBEDDED = import.meta.env.VITE_EMBEDDED === 'true'

function App() {
  const { t } = useTranslation()
  const connected = useConnectionStore((s) => s.connected)
  const connect = useConnectionStore((s) => s.connect)
  const connectEmbedded = useConnectionStore((s) => s.connectEmbedded)
  const getLastDevice = useConnectionStore((s) => s.getLastDevice)
  const fetchConfig = useConfigStore((s) => s.fetchConfig)
  const [activeTab, setActiveTab] = useState(getTabFromHash)
  const [reconnecting, setReconnecting] = useState(() => EMBEDDED || !!getLastDevice())

  useEffect(() => {
    if (!connected) {
      if (EMBEDDED) {
        setReconnecting(true)
        connectEmbedded().catch(() => setReconnecting(false))
      } else {
        const lastDevice = getLastDevice()
        if (lastDevice) {
          setReconnecting(true)
          connect(lastDevice, { silent: true }).catch(() => setReconnecting(false))
        }
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (connected) {
      setReconnecting(false)
      fetchConfig()
      const hashTab = getTabFromHash()
      setActiveTab(hashTab)
      if (!window.location.hash) {
        history.replaceState(null, null, '#editor')
      }
    }
  }, [connected, fetchConfig])

  useEffect(() => {
    const onHashChange = () => setActiveTab(getTabFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const handleTabChange = (tabId) => {
    setActiveTab(tabId)
    history.replaceState(null, null, `#${tabId}`)
  }

  if (!connected) {
    if (EMBEDDED || reconnecting) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-background">
          <div className="flex flex-col items-center gap-4">
            <img src="/logo.svg" alt="v3xctrl" className="h-28" />
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t('discovery.reconnecting')}</p>
          </div>
        </div>
      )
    }
    return (
      <>
        <DeviceDiscovery />
        <Toaster />
      </>
    )
  }

  const ActivePage = TABS.find((t) => t.id === activeTab)?.component || ConfigEditorPage

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar tabs={TABS} activeTab={activeTab} onTabChange={handleTabChange} />
      <div className="container mx-auto flex-1 px-4 py-4">
        {/* Desktop tab bar */}
        <div className="mb-4 hidden gap-1 overflow-x-auto border-b md:flex">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`shrink-0 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {t(tab.labelKey)}
            </button>
          ))}
        </div>
        <ActivePage />
      </div>
      <Footer />
      <Toaster />
    </div>
  )
}

export default App

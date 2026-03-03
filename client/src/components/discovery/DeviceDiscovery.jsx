import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useConnectionStore } from '@/stores/connection'
import { Search, Monitor, ArrowRight, TriangleAlert } from 'lucide-react'

const COMMON_SUBNETS = ['192.168.1', '192.168.0', '10.0.0', '172.16.0']

function checkLocalNetworkAccess() {
  if (location.protocol !== 'https:') {
    return true
  }
  try {
    const req = new Request('http://localhost', { targetAddressSpace: 'local' })
    return 'targetAddressSpace' in req
  } catch {
    return false
  }
}

export function DeviceDiscovery() {
  const { t } = useTranslation()
  const {
    connect,
    scanSubnet,
    isScanning,
    connecting,
    connectionError,
    discoveredDevices,
    scanProgress,
    getLastDevice,
  } = useConnectionStore()

  const [subnetBase, setSubnetBase] = useState('192.168.1')
  const [manualAddress, setManualAddress] = useState('')
  const lastDevice = getLastDevice()
  const supportsLocalAccess = useMemo(() => checkLocalNetworkAccess(), [])

  const handleScan = () => {
    if (subnetBase.trim()) {
      scanSubnet(subnetBase.trim())
    }
  }

  const handleConnect = (url) => {
    connect(url).catch(() => {})
  }

  const handleManualConnect = () => {
    if (manualAddress.trim()) {
      const addr = manualAddress.trim()
      const url = addr.startsWith('http') ? addr : `http://${addr}`
      handleConnect(url)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleManualConnect()
    }
  }

  const busy = connecting || isScanning

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-lg space-y-6">
        <div className="text-center">
          <img src="/logo.svg" alt="v3xctrl" className="mx-auto mb-6 h-28" />
          <h1 className="text-2xl font-bold">{t('discovery.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('discovery.subtitle')}
          </p>
        </div>

        {/* Browser compatibility warning */}
        {!supportsLocalAccess && (
          <div className="flex gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800 dark:border-yellow-900 dark:bg-yellow-950/30 dark:text-yellow-300">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{t('discovery.browserWarning')}</p>
          </div>
        )}

        {/* Connection error */}
        {connectionError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
            {t('discovery.unreachable', { url: connectionError })}
          </div>
        )}

        {/* Last connected device */}
        {lastDevice && (
          <div className="rounded-lg border bg-card p-4">
            <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">
              {t('discovery.lastConnected')}
            </p>
            <button
              onClick={() => handleConnect(lastDevice)}
              disabled={busy}
              className="flex w-full items-center justify-between rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              <span>{lastDevice}</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Subnet scan */}
        <div className="rounded-lg border bg-card p-4">
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium">
              {t('discovery.subnetLabel')}
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                value={subnetBase}
                onChange={(e) => setSubnetBase(e.target.value)}
                placeholder={t('discovery.subnetPlaceholder')}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm sm:flex-1"
                disabled={busy}
              />
              <button
                onClick={handleScan}
                disabled={busy}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Search className="h-4 w-4" />
                {isScanning ? t('discovery.scanning') : t('discovery.scanButton')}
              </button>
            </div>
          </div>

          {/* Common subnets */}
          <div className="mb-3 flex flex-wrap items-center gap-1">
            <span className="w-full text-xs text-muted-foreground sm:w-auto">
              {t('discovery.commonSubnets')}:
            </span>
            {COMMON_SUBNETS.map((subnet) => (
              <button
                key={subnet}
                onClick={() => setSubnetBase(subnet)}
                disabled={busy}
                className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground hover:bg-secondary/80"
              >
                {subnet}
              </button>
            ))}
          </div>

          {/* Progress */}
          {isScanning && (
            <div className="mb-3">
              <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                <span>{t('discovery.scanning')}</span>
                <span>{t('discovery.progress', { current: scanProgress })}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${(scanProgress / 254) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Discovered devices */}
          {discoveredDevices.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">
                {t('discovery.found', { count: discoveredDevices.length })}
              </p>
              {discoveredDevices.map((device) => (
                <button
                  key={device.ip}
                  onClick={() => handleConnect(device.url)}
                  disabled={connecting}
                  className="flex w-full items-center justify-between rounded-md border p-3 text-left hover:bg-accent disabled:opacity-50"
                >
                  <div className="flex items-center gap-3">
                    <Monitor className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">
                        {device.version?.hostname || device.ip}
                      </p>
                      <p className="text-xs text-muted-foreground">{device.ip}</p>
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </button>
              ))}
            </div>
          )}

          {!isScanning && scanProgress > 0 && discoveredDevices.length === 0 && (
            <p className="text-center text-sm text-muted-foreground">
              {t('discovery.noDevices')}
            </p>
          )}
        </div>

        {/* Manual entry */}
        <div className="rounded-lg border bg-card p-4">
          <label className="mb-2 block text-sm font-medium">
            {t('discovery.manualEntry')}
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={manualAddress}
              onChange={(e) => setManualAddress(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('discovery.manualPlaceholder')}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm sm:flex-1"
              disabled={busy}
            />
            <button
              onClick={handleManualConnect}
              disabled={!manualAddress.trim() || busy}
              className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {connecting ? t('discovery.connecting') : t('discovery.connect')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

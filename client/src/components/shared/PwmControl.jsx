import { useTranslation } from 'react-i18next'

export function PwmControl({ label, value, onChange, onSend }) {
  const { t } = useTranslation()

  const handleChange = (newVal) => {
    onChange(newVal)
    onSend(newVal)
  }

  return (
    <div className="mb-3">
      <label className="mb-1 block text-sm font-medium sm:hidden">{label}</label>
      <div className="flex items-center gap-2">
        <label className="hidden w-44 shrink-0 text-sm font-medium sm:block">{label}</label>
        <input
          type="number"
          step={10}
          value={value}
          onChange={(e) => onChange(e.target.value === '' ? '' : parseInt(e.target.value) || 0)}
          className="h-9 w-28 shrink-0 rounded-md border border-input bg-background px-3 text-sm"
        />
        <button
          type="button"
          onClick={() => onSend(value)}
          className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-secondary text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          {t('calibration.send')}
        </button>
        <button
          type="button"
          onClick={() => handleChange(value + 10)}
          className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-secondary text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          +10
        </button>
        <button
          type="button"
          onClick={() => handleChange(value - 10)}
          className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-secondary text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          -10
        </button>
      </div>
    </div>
  )
}

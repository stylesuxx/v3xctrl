import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

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
        <Button variant="secondary" className="flex-1" onClick={() => onSend(value)}>
          {t('calibration.send')}
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => handleChange(value + 10)}>
          +10
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => handleChange(value - 10)}>
          -10
        </Button>
      </div>
    </div>
  )
}

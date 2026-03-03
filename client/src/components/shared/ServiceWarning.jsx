import { AlertTriangle } from 'lucide-react'
export function ServiceWarning({ message, visible }) {
  if (!visible) {
    return null
  }

  return (
    <div className="mb-4 flex items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  )
}

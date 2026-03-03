import { useTranslation } from 'react-i18next'

const LINKS = [
  { labelKey: 'footer.youtube', href: 'https://www.youtube.com/@v3xctrl' },
  { labelKey: 'footer.discord', href: 'https://discord.gg/uF4hf8UBBW' },
  { labelKey: 'footer.instagram', href: 'https://instagram.com/v3xctrl' },
  { labelKey: 'footer.github', href: 'https://github.com/stylesuxx/v3xctrl/issues' },
]

export function Footer() {
  const { t } = useTranslation()
  const year = new Date().getFullYear()

  return (
    <footer className="mt-8 border-t py-4">
      <div className="container mx-auto flex flex-col items-center gap-2 px-4 text-xs text-muted-foreground sm:flex-row sm:justify-between">
        <a href="mailto:info@v3xctrl.com" className="hover:text-foreground">&copy; {year} v3xctrl</a>
        <div className="flex gap-4">
          {LINKS.map((link) => (
            <a
              key={link.labelKey}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground"
            >
              {t(link.labelKey)}
            </a>
          ))}
        </div>
      </div>
    </footer>
  )
}

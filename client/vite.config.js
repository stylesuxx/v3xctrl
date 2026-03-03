import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

const isEmbedded = process.env.VITE_EMBEDDED === 'true'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(!isEmbedded
      ? [
          VitePWA({
            registerType: 'autoUpdate',
            manifest: {
              name: 'v3xctrl',
              short_name: 'v3xctrl',
              description: 'v3xctrl streamer configuration',
              theme_color: '#09090b',
              background_color: '#09090b',
              display: 'standalone',
              icons: [
                { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
                { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
                { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
              ],
            },
            workbox: {
              globPatterns: ['**/*.{js,css,html,png,svg,ico}'],
            },
          }),
        ]
      : []),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.js'],
    globals: true,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: [
        'src/__tests__/**',
        'src/main.jsx',
        'src/App.jsx',
        'src/data/**',
        'src/locales/**',
      ],
      thresholds: {
        statements: 80,
        branches: 70,
        functions: 70,
        lines: 80,
      },
    },
  },
})

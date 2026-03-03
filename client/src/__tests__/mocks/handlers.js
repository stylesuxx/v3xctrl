import { http, HttpResponse } from 'msw'
import { mockConfig, mockSchema, mockServices, mockModemModels, mockModemInfo, mockInfo } from './data'

const BASE = 'http://test-device'

function ok(data) {
  return HttpResponse.json({ data, error: null })
}

export const handlers = [
  // Config
  http.get(`${BASE}/config`, () => ok(mockConfig)),
  http.put(`${BASE}/config`, () => ok({ message: 'Saved!' })),
  http.get(`${BASE}/config/schema`, () => ok(mockSchema)),

  // Services
  http.get(`${BASE}/service`, () => ok({ services: mockServices })),
  http.post(`${BASE}/service/:name/start`, () => ok({ message: 'Started' })),
  http.post(`${BASE}/service/:name/stop`, () => ok({ message: 'Stopped' })),
  http.post(`${BASE}/service/:name/restart`, () => ok({ message: 'Restarted' })),
  http.get(`${BASE}/service/:name/log`, () => ok({ log: 'test log line 1\ntest log line 2' })),
  http.get(`${BASE}/service/:name`, ({ params }) => {
    const service = mockServices.find((s) => s.name === params.name)
    return service
      ? ok(service)
      : ok({ name: params.name, type: 'unknown', state: 'unknown', result: 'error' })
  }),

  // System
  http.post(`${BASE}/system/reboot`, () => ok({ message: 'Rebooting...' })),
  http.post(`${BASE}/system/shutdown`, () => ok({ message: 'Shutting down...' })),
  http.get(`${BASE}/system/dmesg`, () => ok({ log: '[0.000] Linux version...' })),
  http.get(`${BASE}/system/info`, () => ok(mockInfo)),

  // Modem
  http.get(`${BASE}/modem`, () => ok(mockModemInfo)),
  http.get(`${BASE}/modem/models`, () => ok(mockModemModels)),
  http.post(`${BASE}/modem/reset`, () => ok(null)),

  // GPIO
  http.put(`${BASE}/gpio/:channel/pwm`, async ({ params, request }) => {
    const body = await request.json()
    return ok({ gpio: Number(params.channel), value: body.value })
  }),

  // Camera
  http.get(`${BASE}/camera/settings`, () => ok({})),
  http.get(`${BASE}/camera/settings/:name`, ({ params }) => ok({ [params.name]: 0 })),
  http.put(`${BASE}/camera/settings/:name`, async ({ params, request }) => {
    const body = await request.json()
    return ok({ setting: params.name, value: body.value })
  }),
]

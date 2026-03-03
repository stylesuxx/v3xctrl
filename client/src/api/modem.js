export const modemApi = {
  getModemInfo: (client) => client.get('/modem/', { timeout: 90000 }),
  getModemModels: (client) => client.get('/modem/models'),
  resetModem: (client) => client.post('/modem/reset', undefined, { timeout: 90000 }),
}

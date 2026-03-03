export const configApi = {
  getConfig: (client) => client.get('/config/'),
  saveConfig: (client, data) => client.put('/config/', data),
  getSchema: (client) => client.get('/config/schema'),
}

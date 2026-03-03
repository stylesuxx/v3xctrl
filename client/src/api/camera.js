export const cameraApi = {
  getSettings: (client) => client.get('/camera/settings'),
  getSetting: (client, name) => client.get(`/camera/settings/${name}`),
  setSetting: (client, name, value) => client.put(`/camera/settings/${name}`, { value }),
}

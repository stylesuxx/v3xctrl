export const servicesApi = {
  getServices: (client) => client.get('/service').then(d => d.services),
  getService: (client, name) => client.get(`/service/${name}`),
  startService: (client, name) => client.post(`/service/${name}/start`),
  stopService: (client, name) => client.post(`/service/${name}/stop`),
  restartService: (client, name) => client.post(`/service/${name}/restart`),
  getServiceLog: (client, name) => client.get(`/service/${name}/log`).then(d => d.log),
}

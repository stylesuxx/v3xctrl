export const systemApi = {
  reboot: (client) => client.post('/system/reboot'),
  shutdown: (client) => client.post('/system/shutdown'),
  getDmesg: (client) => client.get('/system/dmesg').then(d => d.log),
  getInfo: (client) => client.get('/system/info'),
  getLogArchives: (client) => client.get('/system/logs').then(d => d.archives),
}

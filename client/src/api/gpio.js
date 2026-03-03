export const gpioApi = {
  setPwm: (client, channel, value) => client.put(`/gpio/${channel}/pwm`, { value }),
}

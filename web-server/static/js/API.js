/**
 * Keep the API jQuery agnostic - we wan't to be able to re-use this later on,
 * once we move away from jQuery to some proper, nice framework.
 */

class API {
  static async #get(path) {
    const response = await fetch(path);
    if(!response.ok) {
      throw new Error(`HTTP ${response.status} - ${response.statusText}`);
    }

    return await response.json();
  }

  static async #post(path, data = {}) {
    const response = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} - ${response.statusText}`);
    }

    return await response.json();
  }

  static async getDmesg() {
    const json = await this.#get('/dmesg');

    return json.log;
  }

  static async getModemInfo() {
    const json = await this.#get('/modem/info');

    return json;
  }

  static async getServices() {
    const json = await this.#get('/services');

    return json.services;
  }

  static async startService(name) {
    const json = await this.#post('/service/start', { name });

    return json;
  }

  static async stopService(name) {
    const json = await this.#post('/service/stop', { name });

    return json;
  }

  static async restartService(name) {
    const json = await this.#post('/service/restart', { name });

    return json;
  }

  static async getServiceLog(name) {
    const json = await this.#post('/service/log', { name });

    return json.log;
  }

  static async setPwm(gpio, value) {
    const json = await this.#post('/set-pwm', { gpio, value});

    return json;
  }

  static async setConfig(data) {
    const json = await this.#post('/save', data);

    return json;
  }

  static async reboot() {
    const json = await this.#post('/reboot');

    return json;
  }

  static async shutdown() {
    const json = await this.#post('/shutdown');

    return json;
  }
}

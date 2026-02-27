/**
 * Keep the API jQuery agnostic - we wan't to be able to re-use this later on,
 * once we move away from jQuery to some proper, nice framework.
 */

class API {
  static async #get(path) {
    const response = await fetch(path);
    const json = await response.json();

    if (!response.ok) {
      throw new Error(json.error?.message || `HTTP ${response.status} - ${response.statusText}`);
    }

    return json.data;
  }

  static async #post(path, data = {}) {
    const response = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    const json = await response.json();

    if (!response.ok) {
      throw new Error(json.error?.message || `HTTP ${response.status} - ${response.statusText}`);
    }

    return json.data;
  }

  static async #put(path, data = {}) {
    const response = await fetch(path, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    const json = await response.json();

    if (!response.ok) {
      throw new Error(json.error?.message || `HTTP ${response.status} - ${response.statusText}`);
    }

    return json.data;
  }

  static async getDmesg() {
    const json = await this.#get('/system/dmesg');

    return json.log;
  }

  static async reboot() {
    const json = await this.#post('/system/reboot');

    return json;
  }

  static async shutdown() {
    const json = await this.#post('/system/shutdown');

    return json;
  }

  static async getServices() {
    const json = await this.#get('/service');

    return json.services;
  }

  static async startService(name) {
    const json = await this.#post(`/service/${name}/start`);

    return json;
  }

  static async stopService(name) {
    const json = await this.#post(`/service/${name}/stop`);

    return json;
  }

  static async restartService(name) {
    const json = await this.#post(`/service/${name}/restart`);

    return json;
  }

  static async getServiceLog(name) {
    const json = await this.#get(`/service/${name}/log`);

    return json.log;
  }

  static async getModemInfo() {
    const json = await this.#get('/modem');

    return json;
  }

  static async getVersionInfo() {
    const json = await this.#get('/system/version');

    return json;
  }

  static async resetModem() {
    const json = await this.#post('/modem/reset');

    return json;
  }

  static async setPwm(channel, value) {
    const json = await this.#put(`/gpio/${channel}/pwm`, { value });

    return json;
  }

  static async setConfig(data) {
    const json = await this.#put('/config', data);

    return json;
  }

  static async setCameraSetting(name, value) {
    const json = await this.#put(`/camera/settings/${name}`, { value });

    return json;
  }
}

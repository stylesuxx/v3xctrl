export const mockConfig = {
  viewer: {
    mode: 'direct',
    direct: { host: '192.168.1.100' },
    relay: { sessionId: 'test123', host: 'relay.v3xctrl.com:8888' },
    ports: { video: 16384, control: 16386 },
  },
  network: {
    routing: 'wlan',
    wifi: { mode: 'client' },
    modem: {
      model: 'generic',
      path: '/dev/eigencomm-at',
      limitBands: false,
      allowedBands: [],
    },
    extras: { samba: false, reverseShellUrl: null },
  },
  video: {
    autostart: false,
    testSource: true,
    resolution: '1280x720@30',
    bitrate: 1800000,
    h264Profile: 'high',
    record: { autostart: false, path: '/data/recordings' },
    iFrame: { period: 15, autoAdjust: true, maxBytes: 25600 },
    qp: { min: 20, max: 51 },
  },
  camera: {
    enableHdr: false,
    afMode: 0,
    lensPosition: 0,
    analogueGainMode: 0,
    analogueGain: 1,
    exposureTimeMode: 0,
    exposureTime: 32000,
    sensorMode: '0x0',
    brightness: 0.0,
    contrast: 1.0,
    saturation: 1.0,
    sharpness: 0.0,
  },
  control: {
    autostart: true,
    failsafeTimeout: 150,
    throttle: { min: 1000, max: 2000, failsafe: 1500, idle: 1500, scaleForward: 100, scaleReverse: 100, minForward: 0, minReverse: 0 },
    steering: { min: 1000, max: 2000, failsafe: 1500, trim: 0, scale: 100, invert: false },
    pwm: { throttle: 0, steering: 1 },
    telemetry: {
      battery: {
        i2cAddress: '0x40',
        minVoltage: 3500,
        warnVoltage: 3700,
        maxVoltage: 4200,
        shuntResistance: 100,
        maxExpectedCurrent: 0.8,
      },
    },
  },
  development: { logLevel: 'ERROR' },
}

export const mockSchema = {
  title: 'Configuration',
  type: 'object',
  properties: {
    network: {
      propertyOrder: 10,
      type: 'object',
      title: 'Network',
      properties: {
        routing: {
          propertyOrder: 10,
          type: 'string',
          title: 'Routing',
          enum: ['wlan', 'rndis'],
          options: { enum_titles: ['WiFi', 'LTE/4G'] },
        },
      },
    },
    development: {
      propertyOrder: 50,
      type: 'object',
      title: 'Development',
      properties: {
        logLevel: {
          propertyOrder: 10,
          type: 'string',
          title: 'Log Level',
          enum: ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
        },
      },
    },
  },
}

export const mockServices = [
  { name: 'v3xctrl-setup-env', type: 'oneshot', state: 'active', result: 'success' },
  { name: 'v3xctrl-config-server', type: 'simple', state: 'active', result: 'success' },
  { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
  { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
  { name: 'v3xctrl-debug-log', type: 'simple', state: 'inactive', result: 'success' },
]

export const mockModemModels = {
  generic: {
    validBands: [1, 3, 5, 7, 8, 20, 28, 34, 38, 39, 40, 41],
    hasGps: false,
  },
  'mzuzone-cat1_lte': {
    validBands: [1, 3, 8, 34, 38, 39, 40, 41],
    hasGps: false,
  },
}

export const mockModemInfo = {
  version: 'EC200U V2.0',
  status: 'READY',
  allowedBands: [1, 3, 7, 20],
  activeBand: 'LTE BAND 7',
  carrier: 'Test Carrier',
  contexts: [{ id: 1, type: 'IP', value: '10.0.0.1', apn: 'internet' }],
  addresses: [{ id: 1, ip: '10.0.0.1' }],
}

export const mockInfo = {
  hostname: 'test-streamer',
  packages: {
    'v3xctrl': '1.2.3',
    'v3xctrl-python': '3.11.4',
  },
}

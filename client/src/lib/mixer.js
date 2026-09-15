// Mirrors the MixerType StrEnum in src/v3xctrl_control/mixer/Mixer.py - the values are
// what the config schema and the control service exchange.
export const MixerType = Object.freeze({
  ACKERMANN: 'ackermann',
  DIFFERENTIAL: 'differential',
})

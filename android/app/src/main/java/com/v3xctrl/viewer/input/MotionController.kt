package com.v3xctrl.viewer.input

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.v3xctrl.viewer.control.ControlState

/**
 * Motion-based controller that uses phone orientation to drive steering and throttle.
 * Hold the phone like a steering wheel:
 * - Roll (left/right tilt) controls steering
 * - Pitch (forward/backward tilt) controls throttle
 *
 * Call [zero] to calibrate the current position as neutral.
 */
class MotionController(
    context: Context,
    private val controlState: ControlState,
    steeringDeg: Float = 45f,
    forwardDeg: Float = 45f,
    backwardDeg: Float = 45f,
    private val deadZone: Float = 0.1f
) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val rotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)

    private val rotationMatrix = FloatArray(9)
    private val remappedMatrix = FloatArray(9)
    private val orientation = FloatArray(3)

    private val steeringRad = Math.toRadians(steeringDeg.toDouble()).toFloat()
    private val forwardRad = Math.toRadians(forwardDeg.toDouble()).toFloat()
    private val backwardRad = Math.toRadians(backwardDeg.toDouble()).toFloat()

    // Zero-point calibration (in radians)
    @Volatile private var zeroPitch: Float = 0f
    @Volatile private var zeroRoll: Float = 0f
    @Volatile private var isCalibrated = false

    fun start() {
        rotationSensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
    }

    fun stop() {
        sensorManager.unregisterListener(this)
        controlState.reset()
    }

    /**
     * Calibrate the current phone orientation as neutral (zero point).
     */
    fun zero() {
        isCalibrated = false
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.sensor.type != Sensor.TYPE_GAME_ROTATION_VECTOR) return

        SensorManager.getRotationMatrixFromVector(rotationMatrix, event.values)

        // Remap for landscape orientation (phone held sideways like a steering wheel)
        SensorManager.remapCoordinateSystem(
            rotationMatrix,
            SensorManager.AXIS_Y,
            SensorManager.AXIS_MINUS_X,
            remappedMatrix
        )

        SensorManager.getOrientation(remappedMatrix, orientation)

        val pitch = orientation[1] // Forward/backward tilt
        val roll = orientation[2]  // Left/right tilt (steering wheel rotation)

        if (!isCalibrated) {
            zeroPitch = pitch
            zeroRoll = roll
            isCalibrated = true

            return
        }

        // Compute deltas from zero point
        val deltaPitch = pitch - zeroPitch
        val deltaRoll = roll - zeroRoll

        // Throttle: use separate angles for forward vs backward
        // Positive deltaPitch = tilting forward = throttle up
        val rawThrottle = if (deltaPitch >= 0) {
            (deltaPitch / forwardRad).coerceIn(0f, 1f)
        } else {
            -((-deltaPitch) / backwardRad).coerceIn(0f, 1f)
        }

        // Steering: left/right tilt
        val rawSteering = (deltaRoll / steeringRad).coerceIn(-1f, 1f)

        controlState.throttle = applyDeadZone(rawThrottle, deadZone)
        controlState.steering = applyDeadZone(rawSteering, deadZone)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
        // Not needed
    }
}

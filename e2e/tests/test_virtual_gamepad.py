import unittest

from v3xctrl_e2e.virtual_gamepad import (
    AXIS_MAXIMUM,
    Axis,
    Button,
    VirtualGamepad,
    axis_raw_value,
    binding_for,
    sdl_axis_index,
    sdl_button_index,
)


class TestSdlNumbering(unittest.TestCase):
    def test_axes_follow_ascending_evdev_codes(self):
        self.assertEqual(sdl_axis_index(Axis.STEERING), 0)
        self.assertEqual(sdl_axis_index(Axis.THROTTLE), 1)
        self.assertEqual(sdl_axis_index(Axis.BRAKE), 2)

    def test_buttons_follow_ascending_evdev_codes(self):
        self.assertEqual(sdl_button_index(Button.REC_TOGGLE), 0)
        self.assertEqual(sdl_button_index(Button.TRIM_DECREASE), 1)
        self.assertEqual(sdl_button_index(Button.TRIM_INCREASE), 2)

    def test_binding_carries_the_guid_and_indices(self):
        binding = binding_for("guid-1")

        self.assertEqual(binding.guid, "guid-1")
        self.assertEqual((binding.steering_axis, binding.throttle_axis, binding.brake_axis), (0, 1, 2))
        self.assertEqual(
            (binding.rec_toggle_button, binding.trim_decrease_button, binding.trim_increase_button), (0, 1, 2)
        )


class TestAxisValues(unittest.TestCase):
    def test_scales_and_clamps(self):
        self.assertEqual(axis_raw_value(0.0), 0)
        self.assertEqual(axis_raw_value(1.0), AXIS_MAXIMUM)
        self.assertEqual(axis_raw_value(-1.0), -AXIS_MAXIMUM)
        self.assertEqual(axis_raw_value(2.0), AXIS_MAXIMUM)
        self.assertEqual(axis_raw_value(0.5), round(AXIS_MAXIMUM / 2))


class TestVirtualGamepadWithoutDevice(unittest.TestCase):
    def test_writes_need_an_open_device(self):
        gamepad = VirtualGamepad()

        with self.assertRaises(RuntimeError):
            gamepad.set_axis(Axis.THROTTLE, 0.5)

    def test_close_is_idempotent(self):
        gamepad = VirtualGamepad()

        gamepad.close()
        gamepad.close()

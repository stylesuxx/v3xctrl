import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_gst.QPManager import QPManager


class TestQPManagerInitialization(unittest.TestCase):
    def test_properties_set_correctly(self):
        encoder = MagicMock()
        manager = QPManager(encoder, max_i_frame_bytes=10000, qp_min=10, qp_max=40)

        self.assertEqual(manager.current_qp_min, 10)
        self.assertEqual(manager.qp_max, 40)
        self.assertEqual(manager._max_i_frame_bytes, 10000)
        self.assertEqual(manager._encoder, encoder)

    def test_min_i_frame_bytes_calculation(self):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        self.assertEqual(manager._min_i_frame_bytes, 10000 * 0.85)

    def test_min_i_frame_bytes_with_custom_lower_limit(self):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40, lower_limit_percent=0.70)
        self.assertEqual(manager._min_i_frame_bytes, 7000.0)

    def test_target_i_frame_bytes_calculation(self):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        expected_target = (10000 + 10000 * 0.85) / 2
        self.assertEqual(manager._target_i_frame_bytes, expected_target)

    def test_default_step_and_cooldown_values(self):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        self.assertEqual(manager._min_step, 1)
        self.assertEqual(manager._max_step, 5)
        self.assertEqual(manager._cooldown_keyframes, 0)
        self.assertEqual(manager._keyframes_since_adjust, 0)

    def test_custom_step_and_cooldown_values(self):
        manager = QPManager(
            MagicMock(),
            max_i_frame_bytes=10000,
            qp_min=10,
            qp_max=40,
            min_step=2,
            max_step=8,
            cooldown_keyframes=3,
        )
        self.assertEqual(manager._min_step, 2)
        self.assertEqual(manager._max_step, 8)
        self.assertEqual(manager._cooldown_keyframes, 3)


class TestQPManagerProperties(unittest.TestCase):
    def setUp(self):
        self.manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)

    def test_current_qp_min_returns_initial_value(self):
        self.assertEqual(self.manager.current_qp_min, 10)

    def test_qp_max_returns_limit(self):
        self.assertEqual(self.manager.qp_max, 40)

    def test_current_qp_min_reflects_internal_changes(self):
        self.manager._current_qp_min = 25
        self.assertEqual(self.manager.current_qp_min, 25)


class TestOnKeyframeInRange(unittest.TestCase):
    def setUp(self):
        self.manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)

    def test_frame_in_range_no_adjustment(self):
        initial_qp = self.manager.current_qp_min
        self.manager.on_keyframe(9000)
        self.assertEqual(self.manager.current_qp_min, initial_qp)

    def test_frame_at_max_boundary_no_adjustment(self):
        initial_qp = self.manager.current_qp_min
        self.manager.on_keyframe(10000)
        self.assertEqual(self.manager.current_qp_min, initial_qp)

    def test_frame_at_min_boundary_no_adjustment(self):
        initial_qp = self.manager.current_qp_min
        min_bytes = int(10000 * 0.85)
        self.manager.on_keyframe(min_bytes)
        self.assertEqual(self.manager.current_qp_min, initial_qp)


@patch("v3xctrl_gst.QPManager.Gst")
class TestOnKeyframeTooLarge(unittest.TestCase):
    def test_frame_too_large_increases_qp(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager.on_keyframe(15000)
        self.assertGreater(manager.current_qp_min, 10)

    def test_frame_too_large_applies_encoder_controls(self, mock_gst):
        encoder = MagicMock()
        manager = QPManager(encoder, max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager.on_keyframe(15000)
        encoder.set_property.assert_called_once()


@patch("v3xctrl_gst.QPManager.Gst")
class TestOnKeyframeTooSmall(unittest.TestCase):
    def test_frame_too_small_decreases_qp(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager._current_qp_min = 20
        manager.on_keyframe(1000)
        self.assertLess(manager.current_qp_min, 20)

    def test_frame_too_small_at_qp_min_no_change(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager.on_keyframe(1000)
        self.assertEqual(manager.current_qp_min, 10)


@patch("v3xctrl_gst.QPManager.Gst")
class TestCooldownMechanism(unittest.TestCase):
    def test_cooldown_prevents_immediate_adjustment(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40, cooldown_keyframes=2)
        manager.on_keyframe(15000)
        self.assertEqual(manager.current_qp_min, 10)

    def test_cooldown_allows_adjustment_after_enough_keyframes(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40, cooldown_keyframes=2)
        manager.on_keyframe(15000)
        manager.on_keyframe(15000)
        self.assertEqual(manager.current_qp_min, 10)

        manager.on_keyframe(15000)
        self.assertGreater(manager.current_qp_min, 10)

    def test_cooldown_resets_after_adjustment(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40, cooldown_keyframes=1)
        manager.on_keyframe(15000)
        self.assertEqual(manager.current_qp_min, 10)

        manager.on_keyframe(15000)
        first_adjustment = manager.current_qp_min
        self.assertGreater(first_adjustment, 10)

        manager.on_keyframe(15000)
        self.assertEqual(manager.current_qp_min, first_adjustment)

    def test_zero_cooldown_adjusts_every_keyframe(self, mock_gst):
        encoder = MagicMock()
        manager = QPManager(encoder, max_i_frame_bytes=10000, qp_min=10, qp_max=40, cooldown_keyframes=0)
        manager.on_keyframe(15000)
        self.assertGreater(manager.current_qp_min, 10)


@patch("v3xctrl_gst.QPManager.Gst")
class TestStepSizeClamping(unittest.TestCase):
    def test_step_clamped_to_min_step(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40, min_step=3, max_step=5)
        manager.on_keyframe(10001)
        self.assertGreaterEqual(manager.current_qp_min, 10 + 3)

    def test_step_clamped_to_max_step(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=50, min_step=1, max_step=3)
        manager.on_keyframe(100000)
        self.assertLessEqual(manager.current_qp_min, 10 + 3)


@patch("v3xctrl_gst.QPManager.Gst")
class TestQPBoundaryClamping(unittest.TestCase):
    def test_qp_cannot_exceed_qp_max(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=12, max_step=5)
        manager.on_keyframe(100000)
        self.assertEqual(manager.current_qp_min, 12)

    def test_qp_cannot_go_below_qp_min(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager._current_qp_min = 11
        manager.on_keyframe(100)
        self.assertEqual(manager.current_qp_min, 10)

    def test_repeated_large_frames_stay_at_qp_max(self, mock_gst):
        manager = QPManager(MagicMock(), max_i_frame_bytes=10000, qp_min=10, qp_max=15, max_step=2)
        for _ in range(20):
            manager.on_keyframe(100000)
        self.assertEqual(manager.current_qp_min, 15)


@patch("v3xctrl_gst.QPManager.Gst")
class TestApplyQP(unittest.TestCase):
    def test_encoder_set_property_called(self, mock_gst):
        encoder = MagicMock()
        manager = QPManager(encoder, max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager.on_keyframe(15000)

        encoder.set_property.assert_called_once()
        call_args = encoder.set_property.call_args
        self.assertEqual(call_args[0][0], "extra-controls")

    def test_apply_qp_exception_handling(self, mock_gst):
        encoder = MagicMock()
        encoder.set_property.side_effect = RuntimeError("encoder error")

        manager = QPManager(encoder, max_i_frame_bytes=10000, qp_min=10, qp_max=40)

        with patch("v3xctrl_gst.QPManager.logger") as mock_logger:
            manager.on_keyframe(15000)
            mock_logger.error.assert_called_once()

    def test_apply_qp_not_called_when_qp_unchanged(self, mock_gst):
        encoder = MagicMock()
        manager = QPManager(encoder, max_i_frame_bytes=10000, qp_min=10, qp_max=40)
        manager.on_keyframe(9000)
        encoder.set_property.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from collections import deque
from dataclasses import FrozenInstanceError

import numpy as np

from v3xctrl_ui.core.FrameSnapshot import ConnectionStatus, FrameSnapshot


class TestConnectionStatus(unittest.TestCase):
    def test_defaults_describe_a_disconnected_viewer(self):
        status = ConnectionStatus()

        self.assertFalse(status.user_connected)
        self.assertFalse(status.control_connected)
        self.assertFalse(status.spectator)
        self.assertIsNone(status.control_error)
        self.assertFalse(status.relay_enabled)
        self.assertEqual(status.relay_status_message, "")
        self.assertEqual(status.control_queue_depth, 0)
        self.assertEqual(status.video_buffer_depth, 0)

    def test_is_frozen(self):
        status = ConnectionStatus()

        with self.assertRaises(FrozenInstanceError):
            status.user_connected = True

    def test_has_no_instance_dict(self):
        """slots keeps per-frame construction cheap."""
        self.assertFalse(hasattr(ConnectionStatus(), "__dict__"))


class TestFrameSnapshot(unittest.TestCase):
    def test_defaults_describe_an_idle_frame(self):
        snapshot = FrameSnapshot()

        self.assertIsNone(snapshot.video_frame)
        self.assertIsNone(snapshot.video_history)
        self.assertFalse(snapshot.menu_visible)
        self.assertFalse(snapshot.fullscreen)
        self.assertEqual(snapshot.scale, 1.0)
        self.assertEqual(snapshot.throttle, 0.0)
        self.assertEqual(snapshot.steering, 0.0)
        self.assertEqual(len(snapshot.loop_history), 0)

    def test_is_frozen(self):
        snapshot = FrameSnapshot()

        with self.assertRaises(FrozenInstanceError):
            snapshot.throttle = 1.0

    def test_has_no_instance_dict(self):
        self.assertFalse(hasattr(FrameSnapshot(), "__dict__"))

    def test_each_snapshot_gets_its_own_loop_history(self):
        first = FrameSnapshot()
        second = FrameSnapshot()

        first.loop_history.append(1.0)

        self.assertEqual(len(second.loop_history), 0)

    def test_holds_the_frame_by_reference(self):
        """A copy here would cost megabytes per frame and defeat the blit skip."""
        frame = np.zeros((4, 4, 3), dtype=np.uint8)

        snapshot = FrameSnapshot(video_frame=frame)

        self.assertIs(snapshot.video_frame, frame)

    def test_holds_the_histories_by_reference(self):
        loop_history = deque([1.0])
        video_history = deque([2.0])

        snapshot = FrameSnapshot(loop_history=loop_history, video_history=video_history)

        self.assertIs(snapshot.loop_history, loop_history)
        self.assertIs(snapshot.video_history, video_history)


if __name__ == "__main__":
    unittest.main()

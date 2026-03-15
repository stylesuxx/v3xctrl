import threading
import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_gst.RecordingManager import RecordingManager


class TestRecordingManagerConstructor(unittest.TestCase):
    def test_initial_state(self):
        pipeline = MagicMock()
        tee = MagicMock()
        manager = RecordingManager(pipeline, tee, "/tmp/recordings")

        self.assertFalse(manager.is_recording)
        self.assertEqual(manager._elements, {})
        self.assertIsNone(manager._tee_pad)
        self.assertIsNone(manager._stop_complete)

    def test_default_sizebuffers(self):
        manager = RecordingManager(MagicMock(), MagicMock(), "/tmp/recordings")
        self.assertEqual(manager._sizebuffers, 30)

    def test_custom_sizebuffers(self):
        manager = RecordingManager(MagicMock(), MagicMock(), "/tmp/recordings", sizebuffers=60)
        self.assertEqual(manager._sizebuffers, 60)

    def test_default_on_queue_overrun_is_none(self):
        manager = RecordingManager(MagicMock(), MagicMock(), "/tmp/recordings")
        self.assertIsNone(manager._on_queue_overrun)

    def test_custom_on_queue_overrun(self):
        callback = MagicMock()
        manager = RecordingManager(MagicMock(), MagicMock(), "/tmp/recordings", on_queue_overrun=callback)
        self.assertIs(manager._on_queue_overrun, callback)


class TestIsRecordingProperty(unittest.TestCase):
    def test_returns_false_initially(self):
        manager = RecordingManager(MagicMock(), MagicMock(), "/tmp/recordings")
        self.assertFalse(manager.is_recording)

    def test_reflects_internal_state(self):
        manager = RecordingManager(MagicMock(), MagicMock(), "/tmp/recordings")
        manager._is_recording = True
        self.assertTrue(manager.is_recording)


class TestRecordingManagerStart(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object
        self.mock_gst.PadLinkReturn.OK = "ok"

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.recording_dir = "/tmp/test_recordings"
        self.manager = RecordingManager(self.pipeline, self.tee, self.recording_dir)

        self.mock_queue = MagicMock()
        self.mock_parser = MagicMock()
        self.mock_muxer = MagicMock()
        self.mock_filesink = MagicMock()

        self.mock_queue.link.return_value = True
        self.mock_parser.link.return_value = True
        self.mock_muxer.link.return_value = True

        self.tee_src_pad = MagicMock()
        self.tee.request_pad_simple.return_value = self.tee_src_pad
        self.tee_src_pad.link.return_value = "ok"

        self.queue_sink_pad = MagicMock()
        self.mock_queue.get_static_pad.return_value = self.queue_sink_pad

        def element_factory_side_effect(element_type, name):
            elements = {
                "queue": self.mock_queue,
                "h264parse": self.mock_parser,
                "mpegtsmux": self.mock_muxer,
                "filesink": self.mock_filesink,
            }
            return elements.get(element_type)

        self.mock_gst.ElementFactory.make.side_effect = element_factory_side_effect

    def tearDown(self):
        self.gst_patcher.stop()

    def test_already_recording_returns_false(self):
        self.manager._is_recording = True
        result = self.manager.start()
        self.assertFalse(result)

    def test_empty_recording_dir_returns_false(self):
        manager = RecordingManager(self.pipeline, self.tee, "")
        result = manager.start()
        self.assertFalse(result)

    @patch("os.makedirs")
    def test_successful_start(self, mock_makedirs):
        result = self.manager.start()

        self.assertTrue(result)
        self.assertTrue(self.manager.is_recording)
        mock_makedirs.assert_called_once_with(self.recording_dir, exist_ok=True)

    @patch("os.makedirs")
    def test_elements_added_to_pipeline(self, mock_makedirs):
        self.manager.start()

        self.pipeline.add.assert_any_call(self.mock_queue)
        self.pipeline.add.assert_any_call(self.mock_parser)
        self.pipeline.add.assert_any_call(self.mock_muxer)
        self.pipeline.add.assert_any_call(self.mock_filesink)
        self.assertEqual(self.pipeline.add.call_count, 4)

    @patch("os.makedirs")
    def test_elements_linked_in_order(self, mock_makedirs):
        self.manager.start()

        self.mock_queue.link.assert_called_once_with(self.mock_parser)
        self.mock_parser.link.assert_called_once_with(self.mock_muxer)
        self.mock_muxer.link.assert_called_once_with(self.mock_filesink)

    @patch("os.makedirs")
    def test_elements_synced_with_parent(self, mock_makedirs):
        self.manager.start()

        self.mock_queue.sync_state_with_parent.assert_called_once()
        self.mock_parser.sync_state_with_parent.assert_called_once()
        self.mock_muxer.sync_state_with_parent.assert_called_once()
        self.mock_filesink.sync_state_with_parent.assert_called_once()

    @patch("os.makedirs")
    def test_tee_pad_requested_and_linked(self, mock_makedirs):
        self.manager.start()

        self.tee.request_pad_simple.assert_called_once_with("src_%u")
        self.tee_src_pad.link.assert_called_once_with(self.queue_sink_pad)
        self.assertIs(self.manager._tee_pad, self.tee_src_pad)

    @patch("os.makedirs")
    def test_filesink_properties_set(self, mock_makedirs):
        self.manager.start()

        self.mock_filesink.set_property.assert_any_call("location", unittest.mock.ANY)
        self.mock_filesink.set_property.assert_any_call("sync", False)
        self.mock_filesink.set_property.assert_any_call("async", False)

    @patch("os.makedirs")
    def test_queue_properties_set(self, mock_makedirs):
        self.manager.start()

        self.mock_queue.set_property.assert_any_call("max-size-buffers", 30)
        self.mock_queue.set_property.assert_any_call("leaky", 2)

    @patch("os.makedirs")
    def test_filename_stored_in_elements(self, mock_makedirs):
        self.manager.start()

        filename = self.manager._elements.get("filename")
        self.assertIsNotNone(filename)
        self.assertTrue(filename.startswith(self.recording_dir + "/stream-"))
        self.assertTrue(filename.endswith(".ts"))

    @patch("os.makedirs")
    def test_with_queue_overrun_callback(self, mock_makedirs):
        callback = MagicMock()
        manager = RecordingManager(self.pipeline, self.tee, self.recording_dir, on_queue_overrun=callback)
        manager.start()

        self.mock_queue.connect.assert_called_once_with("overrun", callback)

    @patch("os.makedirs")
    def test_without_queue_overrun_callback(self, mock_makedirs):
        self.manager.start()

        self.mock_queue.connect.assert_not_called()


class TestStartElementCreationFailure(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

    def tearDown(self):
        self.gst_patcher.stop()

    @patch("os.makedirs")
    def test_queue_creation_failure(self, mock_makedirs):
        def factory(element_type, name):
            if element_type == "queue":
                return None
            return MagicMock()

        self.mock_gst.ElementFactory.make.side_effect = factory
        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)

    @patch("os.makedirs")
    def test_parser_creation_failure(self, mock_makedirs):
        def factory(element_type, name):
            if element_type == "h264parse":
                return None
            return MagicMock()

        self.mock_gst.ElementFactory.make.side_effect = factory
        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)

    @patch("os.makedirs")
    def test_muxer_creation_failure(self, mock_makedirs):
        def factory(element_type, name):
            if element_type == "mpegtsmux":
                return None
            return MagicMock()

        self.mock_gst.ElementFactory.make.side_effect = factory
        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)

    @patch("os.makedirs")
    def test_filesink_creation_failure(self, mock_makedirs):
        def factory(element_type, name):
            if element_type == "filesink":
                return None
            return MagicMock()

        self.mock_gst.ElementFactory.make.side_effect = factory
        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)


class TestStartLinkFailure(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object
        self.mock_gst.PadLinkReturn.OK = "ok"

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

        self.mock_queue = MagicMock()
        self.mock_parser = MagicMock()
        self.mock_muxer = MagicMock()
        self.mock_filesink = MagicMock()

        def factory(element_type, name):
            elements = {
                "queue": self.mock_queue,
                "h264parse": self.mock_parser,
                "mpegtsmux": self.mock_muxer,
                "filesink": self.mock_filesink,
            }
            return elements.get(element_type)

        self.mock_gst.ElementFactory.make.side_effect = factory

    def tearDown(self):
        self.gst_patcher.stop()

    @patch("os.makedirs")
    def test_queue_to_parser_link_failure(self, mock_makedirs):
        self.mock_queue.link.return_value = False

        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)

    @patch("os.makedirs")
    def test_parser_to_muxer_link_failure(self, mock_makedirs):
        self.mock_queue.link.return_value = True
        self.mock_parser.link.return_value = False

        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)

    @patch("os.makedirs")
    def test_muxer_to_filesink_link_failure(self, mock_makedirs):
        self.mock_queue.link.return_value = True
        self.mock_parser.link.return_value = True
        self.mock_muxer.link.return_value = False

        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)


class TestStartTeePadFailure(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object
        self.mock_gst.PadLinkReturn.OK = "ok"

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

        self.mock_queue = MagicMock()
        self.mock_parser = MagicMock()
        self.mock_muxer = MagicMock()
        self.mock_filesink = MagicMock()

        self.mock_queue.link.return_value = True
        self.mock_parser.link.return_value = True
        self.mock_muxer.link.return_value = True

        def factory(element_type, name):
            elements = {
                "queue": self.mock_queue,
                "h264parse": self.mock_parser,
                "mpegtsmux": self.mock_muxer,
                "filesink": self.mock_filesink,
            }
            return elements.get(element_type)

        self.mock_gst.ElementFactory.make.side_effect = factory

    def tearDown(self):
        self.gst_patcher.stop()

    @patch("os.makedirs")
    def test_request_pad_simple_returns_none(self, mock_makedirs):
        self.tee.request_pad_simple.return_value = None

        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)

    @patch("os.makedirs")
    def test_pad_link_returns_non_ok(self, mock_makedirs):
        tee_src_pad = MagicMock()
        self.tee.request_pad_simple.return_value = tee_src_pad
        tee_src_pad.link.return_value = "error"

        result = self.manager.start()

        self.assertFalse(result)
        self.assertFalse(self.manager.is_recording)


class TestStop(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

    def tearDown(self):
        self.gst_patcher.stop()

    def test_not_recording_returns_false(self):
        result = self.manager.stop()
        self.assertFalse(result)

    def test_no_tee_pad_returns_false(self):
        self.manager._is_recording = True
        self.manager._tee_pad = None

        result = self.manager.stop()

        self.assertFalse(result)

    def test_successful_stop_sets_not_recording(self):
        self.manager._is_recording = True
        tee_pad = MagicMock()
        self.manager._tee_pad = tee_pad

        def fake_add_probe(probe_type, callback):
            self.manager._stop_complete.set()
            return MagicMock()

        tee_pad.add_probe.side_effect = fake_add_probe

        result = self.manager.stop()

        self.assertTrue(result)
        self.assertFalse(self.manager.is_recording)

    def test_stop_adds_probe_to_tee_pad(self):
        self.manager._is_recording = True
        tee_pad = MagicMock()
        self.manager._tee_pad = tee_pad

        def fake_add_probe(probe_type, callback):
            self.manager._stop_complete.set()
            return MagicMock()

        tee_pad.add_probe.side_effect = fake_add_probe

        self.manager.stop()

        tee_pad.add_probe.assert_called_once()
        probe_args = tee_pad.add_probe.call_args
        self.assertEqual(probe_args[0][0], self.mock_gst.PadProbeType.BLOCK_DOWNSTREAM)

    def test_stop_creates_stop_complete_event(self):
        self.manager._is_recording = True
        tee_pad = MagicMock()
        self.manager._tee_pad = tee_pad

        def fake_add_probe(probe_type, callback):
            self.assertIsInstance(self.manager._stop_complete, threading.Event)
            self.manager._stop_complete.set()
            return MagicMock()

        tee_pad.add_probe.side_effect = fake_add_probe
        self.manager.stop()


class TestCleanup(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

    def tearDown(self):
        self.gst_patcher.stop()

    def test_resets_is_recording(self):
        self.manager._is_recording = True
        self.manager._cleanup()
        self.assertFalse(self.manager.is_recording)

    def test_releases_tee_pad(self):
        tee_pad = MagicMock()
        self.manager._tee_pad = tee_pad

        self.manager._cleanup()

        self.tee.release_request_pad.assert_called_once_with(tee_pad)
        self.assertIsNone(self.manager._tee_pad)

    def test_no_tee_pad_skips_release(self):
        self.manager._tee_pad = None
        self.manager._cleanup()
        self.tee.release_request_pad.assert_not_called()

    def test_sets_elements_to_null_and_removes(self):
        element1 = MagicMock()
        element2 = MagicMock()
        element1.get_parent.return_value = self.pipeline
        element2.get_parent.return_value = self.pipeline

        self.manager._elements = {
            "queue": element1,
            "parser": element2,
            "filename": "/tmp/test.ts",
        }

        self.manager._cleanup()

        element1.set_state.assert_called_once_with(self.mock_gst.State.NULL)
        element2.set_state.assert_called_once_with(self.mock_gst.State.NULL)
        self.pipeline.remove.assert_any_call(element1)
        self.pipeline.remove.assert_any_call(element2)

    def test_skips_filename_entry(self):
        self.manager._elements = {"filename": "/tmp/test.ts"}
        self.manager._cleanup()
        self.pipeline.remove.assert_not_called()

    def test_clears_elements_dict(self):
        self.manager._elements = {"queue": MagicMock(), "filename": "/tmp/test.ts"}
        self.manager._cleanup()
        self.assertEqual(self.manager._elements, {})

    def test_does_not_remove_element_without_parent(self):
        element = MagicMock()
        element.get_parent.return_value = None
        self.manager._elements = {"queue": element}

        self.manager._cleanup()

        element.set_state.assert_called_once_with(self.mock_gst.State.NULL)
        self.pipeline.remove.assert_not_called()


class TestTeardown(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

    def tearDown(self):
        self.gst_patcher.stop()

    def test_sets_elements_to_null_state(self):
        element1 = MagicMock()
        element2 = MagicMock()
        self.manager._elements = {
            "queue": element1,
            "parser": element2,
            "filename": "/tmp/test.ts",
        }

        self.manager._teardown()

        element1.set_state.assert_called_once_with(self.mock_gst.State.NULL)
        element2.set_state.assert_called_once_with(self.mock_gst.State.NULL)

    def test_removes_elements_from_pipeline(self):
        element = MagicMock()
        self.manager._elements = {"queue": element, "filename": "/tmp/test.ts"}

        self.manager._teardown()

        self.pipeline.remove.assert_called_once_with(element)

    def test_clears_elements_dict(self):
        self.manager._elements = {"queue": MagicMock(), "filename": "/tmp/test.ts"}
        self.manager._teardown()
        self.assertEqual(self.manager._elements, {})

    def test_sets_stop_complete_event(self):
        self.manager._elements = {"filename": "/tmp/test.ts"}
        self.manager._stop_complete = threading.Event()

        self.manager._teardown()

        self.assertTrue(self.manager._stop_complete.is_set())

    def test_returns_false(self):
        self.manager._elements = {}
        result = self.manager._teardown()
        self.assertFalse(result)

    def test_no_stop_complete_does_not_raise(self):
        self.manager._elements = {}
        self.manager._stop_complete = None
        self.manager._teardown()


class TestForceTeardown(unittest.TestCase):
    def setUp(self):
        self.gst_patcher = patch("v3xctrl_gst.RecordingManager.Gst")
        self.mock_gst = self.gst_patcher.start()
        self.mock_gst.Element = object

        self.pipeline = MagicMock()
        self.tee = MagicMock()
        self.manager = RecordingManager(self.pipeline, self.tee, "/tmp/recordings")

    def tearDown(self):
        self.gst_patcher.stop()

    def test_unlinks_and_releases_tee_pad(self):
        tee_pad = MagicMock()
        queue = MagicMock()
        queue_sink_pad = MagicMock()
        queue.get_static_pad.return_value = queue_sink_pad

        self.manager._tee_pad = tee_pad
        self.manager._elements = {"queue": queue, "filename": "/tmp/test.ts"}

        self.manager._force_teardown()

        tee_pad.unlink.assert_called_once_with(queue_sink_pad)
        self.tee.release_request_pad.assert_called_once_with(tee_pad)
        self.assertIsNone(self.manager._tee_pad)

    def test_no_tee_pad_skips_unlink(self):
        self.manager._tee_pad = None
        self.manager._elements = {"filename": "/tmp/test.ts"}

        self.manager._force_teardown()

        self.tee.release_request_pad.assert_not_called()

    def test_sets_elements_to_null_and_removes(self):
        element = MagicMock()
        element.get_parent.return_value = self.pipeline
        self.manager._elements = {"queue": element, "filename": "/tmp/test.ts"}

        self.manager._force_teardown()

        element.set_state.assert_called_once_with(self.mock_gst.State.NULL)
        self.pipeline.remove.assert_called_once_with(element)

    def test_does_not_remove_element_without_parent(self):
        element = MagicMock()
        element.get_parent.return_value = None
        self.manager._elements = {"queue": element}

        self.manager._force_teardown()

        element.set_state.assert_called_once_with(self.mock_gst.State.NULL)
        self.pipeline.remove.assert_not_called()

    def test_clears_elements_dict(self):
        self.manager._elements = {"queue": MagicMock(), "filename": "/tmp/test.ts"}
        self.manager._force_teardown()
        self.assertEqual(self.manager._elements, {})

    def test_handles_missing_queue_gracefully(self):
        tee_pad = MagicMock()
        self.manager._tee_pad = tee_pad
        self.manager._elements = {"filename": "/tmp/test.ts"}

        self.manager._force_teardown()

        self.tee.release_request_pad.assert_called_once_with(tee_pad)


if __name__ == "__main__":
    unittest.main()

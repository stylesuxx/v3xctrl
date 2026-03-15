import unittest
from unittest.mock import MagicMock, patch


class TestSourceRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_camera_builder = MagicMock(name="CameraSourceBuilder")
        cls.mock_file_builder = MagicMock(name="FileSourceBuilder")
        cls.mock_test_builder = MagicMock(name="TestSourceBuilder")

    def _get_registry(self):
        with (
            patch.dict(
                "sys.modules",
                {
                    "gi": MagicMock(),
                    "gi.repository": MagicMock(),
                },
            ),
            patch("v3xctrl_gst.Sources.CameraSourceBuilder", self.mock_camera_builder),
            patch("v3xctrl_gst.Sources.FileSourceBuilder", self.mock_file_builder),
            patch("v3xctrl_gst.Sources.TestSourceBuilder", self.mock_test_builder),
        ):
            import importlib

            import v3xctrl_gst.SourceRegistry as module

            importlib.reload(module)
            return module.SourceRegistry

    def test_list_sources_returns_all_names(self):
        registry = self._get_registry()
        sources = registry.list_sources()
        self.assertEqual(sorted(sources), ["camera", "file", "test"])

    def test_list_sources_returns_list(self):
        registry = self._get_registry()
        self.assertIsInstance(registry.list_sources(), list)

    def test_create_camera_returns_correct_builder(self):
        registry = self._get_registry()
        settings = {"resolution": "1080p"}
        registry.create("camera", settings)
        self.mock_camera_builder.assert_called_with(settings)

    def test_create_file_returns_correct_builder(self):
        registry = self._get_registry()
        settings = {"path": "/tmp/video.mp4"}
        registry.create("file", settings)
        self.mock_file_builder.assert_called_with(settings)

    def test_create_test_returns_correct_builder(self):
        registry = self._get_registry()
        settings = {}
        registry.create("test", settings)
        self.mock_test_builder.assert_called_with(settings)

    def test_create_unknown_source_raises_value_error(self):
        registry = self._get_registry()
        with self.assertRaises(ValueError) as context:
            registry.create("nonexistent", {})
        self.assertIn("nonexistent", str(context.exception))

    def test_error_message_lists_available_sources(self):
        registry = self._get_registry()
        with self.assertRaises(ValueError) as context:
            registry.create("invalid", {})
        error_message = str(context.exception)
        self.assertIn("camera", error_message)
        self.assertIn("file", error_message)
        self.assertIn("test", error_message)

    def test_create_returns_builder_instance(self):
        registry = self._get_registry()
        expected_instance = MagicMock()
        self.mock_test_builder.return_value = expected_instance
        result = registry.create("test", {})
        self.assertIs(result, expected_instance)


if __name__ == "__main__":
    unittest.main()

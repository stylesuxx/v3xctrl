import os
import tempfile
import unittest
from unittest.mock import patch

from v3xctrl_ui.utils.gstreamer import _is_running_in_flatpak, _use_versioned_registry


class TestIsRunningInFlatpak(unittest.TestCase):
    def test_detects_sandbox_from_flatpak_info(self) -> None:
        with patch("os.path.exists", return_value=True) as exists:
            self.assertTrue(_is_running_in_flatpak())
        exists.assert_called_once_with("/.flatpak-info")

    def test_reports_false_outside_sandbox(self) -> None:
        with patch("os.path.exists", return_value=False):
            self.assertFalse(_is_running_in_flatpak())


class TestUseVersionedRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self._original_registry = os.environ.get("GST_REGISTRY")

    def tearDown(self) -> None:
        if self._original_registry is None:
            os.environ.pop("GST_REGISTRY", None)
        else:
            os.environ["GST_REGISTRY"] = self._original_registry

    def test_registry_path_is_keyed_on_version(self) -> None:
        with tempfile.TemporaryDirectory() as cache_home:
            expected = os.path.join(cache_home, "gstreamer-1.0", "registry-1.2.3.bin")

            with (
                patch.dict(os.environ, {"XDG_CACHE_HOME": cache_home}),
                patch("v3xctrl_ui.utils.gstreamer.__version__", "1.2.3"),
            ):
                _use_versioned_registry()
                self.assertEqual(os.environ["GST_REGISTRY"], expected)

            self.assertTrue(os.path.isdir(os.path.join(cache_home, "gstreamer-1.0")))

    def test_registry_of_previous_version_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as cache_home:
            registry_directory = os.path.join(cache_home, "gstreamer-1.0")
            os.makedirs(registry_directory)
            outdated = os.path.join(registry_directory, "registry-1.0.0.bin")
            shared = os.path.join(registry_directory, "registry.x86_64.bin")
            for path in (outdated, shared):
                with open(path, "w") as handle:
                    handle.write("stale")

            with (
                patch.dict(os.environ, {"XDG_CACHE_HOME": cache_home}),
                patch("v3xctrl_ui.utils.gstreamer.__version__", "1.1.0"),
            ):
                _use_versioned_registry()

            self.assertFalse(os.path.exists(outdated))
            self.assertTrue(os.path.exists(shared))

    def test_registry_is_left_unset_when_directory_cannot_be_created(self) -> None:
        os.environ.pop("GST_REGISTRY", None)

        with patch("os.makedirs", side_effect=OSError("read-only")):
            _use_versioned_registry()

        self.assertNotIn("GST_REGISTRY", os.environ)


if __name__ == "__main__":
    unittest.main()

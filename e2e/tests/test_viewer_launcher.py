import unittest
from pathlib import Path

from v3xctrl_e2e.viewer_launcher import ViewerKind, ViewerLauncher


class TestViewerLauncherCommand(unittest.TestCase):
    def test_source_viewer_runs_the_module_with_connect(self):
        launcher = ViewerLauncher(ViewerKind.SOURCE, "/venv/bin/python", Path("/repo/src"), headless=False)

        command = launcher.command(Path("/runs/t/settings.toml"))

        self.assertEqual(command[:3], ["/venv/bin/python", "-m", "v3xctrl_ui.main"])
        self.assertIn("--connect", command)
        self.assertIn("/runs/t/settings.toml", command)

    def test_title_is_passed_only_when_the_build_supports_it(self):
        launcher = ViewerLauncher(ViewerKind.SOURCE, "/venv/bin/python", Path("/repo/src"), headless=False)

        with_title = launcher.command(Path("/runs/t/settings.toml"), "L1-direct-udp-udp (1/9)")
        launcher.supports_title = False
        without_title = launcher.command(Path("/runs/t/settings.toml"), "L1-direct-udp-udp (1/9)")

        self.assertEqual(with_title[-2:], ["--title", "L1-direct-udp-udp (1/9)"])
        self.assertNotIn("--title", without_title)
        self.assertNotIn("--title", launcher.command(Path("/runs/t/settings.toml")))

    def test_flatpak_viewer_gets_the_config_directory_and_sdl_settings(self):
        launcher = ViewerLauncher(ViewerKind.FLATPAK, "python", Path("/repo/src"), headless=False)

        command = launcher.command(Path("/runs/t/settings.toml"))

        self.assertEqual(command[:2], ["flatpak", "run"])
        self.assertIn("--filesystem=/runs/t", command)
        self.assertIn("--env=SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1", command)
        self.assertIn("com.v3xctrl.viewer", command)


class TestViewerLauncherHelp(unittest.TestCase):
    def test_help_commands(self):
        source = ViewerLauncher(ViewerKind.SOURCE, "/venv/bin/python", Path("/repo/src"), headless=False)
        flatpak = ViewerLauncher(ViewerKind.FLATPAK, "python", Path("/repo/src"), headless=False)

        self.assertEqual(source.help_command(), ["/venv/bin/python", "-m", "v3xctrl_ui.main", "--help"])
        self.assertEqual(flatpak.help_command(), ["flatpak", "run", "com.v3xctrl.viewer", "--help"])


class TestViewerLauncherEnvironment(unittest.TestCase):
    def test_joystick_input_is_allowed_without_focus(self):
        launcher = ViewerLauncher(ViewerKind.SOURCE, "python", Path("/repo/src"), headless=False)

        environment = launcher.environment()

        self.assertEqual(environment["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"], "1")
        self.assertEqual(environment["SDL_AUDIODRIVER"], "dummy")
        self.assertNotIn("SDL_VIDEODRIVER", launcher.sdl_settings())

    def test_headless_uses_the_dummy_video_driver(self):
        launcher = ViewerLauncher(ViewerKind.SOURCE, "python", Path("/repo/src"), headless=True)

        self.assertEqual(launcher.environment()["SDL_VIDEODRIVER"], "dummy")

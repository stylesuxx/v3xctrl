"""Tests for TelemetryContext."""
import unittest
import threading
import time

from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.core.dataclasses import (
    ServiceFlags,
    GstFlags,
    VideoCoreFlags,
    BatteryData,
    SignalData,
)


class TestServiceFlags(unittest.TestCase):
    """Test ServiceFlags dataclass and parsing."""

    def test_from_byte_no_services(self):
        """Test parsing byte with no services active."""
        flags = ServiceFlags.from_byte(0b00000000)
        self.assertFalse(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertFalse(flags.debug)

    def test_from_byte_video_only(self):
        """Test parsing byte with only video service active."""
        flags = ServiceFlags.from_byte(0b00000001)
        self.assertTrue(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertFalse(flags.debug)

    def test_from_byte_reverse_shell_only(self):
        """Test parsing byte with only reverse_shell service active."""
        flags = ServiceFlags.from_byte(0b00000010)
        self.assertFalse(flags.video)
        self.assertTrue(flags.reverse_shell)
        self.assertFalse(flags.debug)

    def test_from_byte_debug_only(self):
        """Test parsing byte with only debug service active."""
        flags = ServiceFlags.from_byte(0b00000100)
        self.assertFalse(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertTrue(flags.debug)

    def test_from_byte_all_services(self):
        """Test parsing byte with all services active."""
        flags = ServiceFlags.from_byte(0b00000111)
        self.assertTrue(flags.video)
        self.assertTrue(flags.reverse_shell)
        self.assertTrue(flags.debug)

    def test_from_byte_video_and_debug(self):
        """Test parsing byte with video and debug active."""
        flags = ServiceFlags.from_byte(0b00000101)
        self.assertTrue(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertTrue(flags.debug)

    def test_default_values(self):
        """Test default values."""
        flags = ServiceFlags()
        self.assertFalse(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertFalse(flags.debug)


class TestGstFlags(unittest.TestCase):
    """Test GstFlags dataclass and parsing."""

    def test_from_byte_not_recording(self):
        """Test parsing byte with recording inactive."""
        flags = GstFlags.from_byte(0b00000000)
        self.assertFalse(flags.recording)

    def test_from_byte_recording(self):
        """Test parsing byte with recording active."""
        flags = GstFlags.from_byte(0b00000001)
        self.assertTrue(flags.recording)

    def test_default_values(self):
        """Test default values."""
        flags = GstFlags()
        self.assertFalse(flags.recording)


class TestVideoCoreFlags(unittest.TestCase):
    """Test VideoCoreFlags dataclass and parsing."""

    def test_from_byte_no_flags(self):
        """Test parsing byte with no flags."""
        flags = VideoCoreFlags.from_byte(0b00000000)
        self.assertEqual(flags.current, 0)
        self.assertEqual(flags.history, 0)

    def test_from_byte_current_only(self):
        """Test parsing byte with only current flags."""
        flags = VideoCoreFlags.from_byte(0b00001111)
        self.assertEqual(flags.current, 0x0F)
        self.assertEqual(flags.history, 0)

    def test_from_byte_history_only(self):
        """Test parsing byte with only history flags."""
        flags = VideoCoreFlags.from_byte(0b11110000)
        self.assertEqual(flags.current, 0)
        self.assertEqual(flags.history, 0x0F)

    def test_from_byte_both_flags(self):
        """Test parsing byte with both current and history flags."""
        flags = VideoCoreFlags.from_byte(0b10100101)
        self.assertEqual(flags.current, 0x05)
        self.assertEqual(flags.history, 0x0A)

    def test_default_values(self):
        """Test default values."""
        flags = VideoCoreFlags()
        self.assertEqual(flags.current, 0)
        self.assertEqual(flags.history, 0)


class TestBatteryData(unittest.TestCase):
    """Test BatteryData dataclass."""

    def test_default_values(self):
        """Test default values."""
        battery = BatteryData()
        self.assertEqual(battery.icon, 0)
        self.assertEqual(battery.voltage, "0.00V")
        self.assertEqual(battery.average_voltage, "0.00V")
        self.assertEqual(battery.percent, "0%")
        self.assertFalse(battery.warning)

    def test_custom_values(self):
        """Test custom values."""
        battery = BatteryData(
            icon=75,
            voltage="12.34V",
            average_voltage="12.30V",
            percent="75%",
            warning=True
        )
        self.assertEqual(battery.icon, 75)
        self.assertEqual(battery.voltage, "12.34V")
        self.assertEqual(battery.average_voltage, "12.30V")
        self.assertEqual(battery.percent, "75%")
        self.assertTrue(battery.warning)


class TestSignalData(unittest.TestCase):
    """Test SignalData dataclass."""

    def test_default_values(self):
        """Test default values."""
        signal = SignalData()
        self.assertEqual(signal.quality, {"rsrq": -1, "rsrp": -1})
        self.assertEqual(signal.band, "BAND ?")
        self.assertEqual(signal.cell, "CELL ?")

    def test_custom_values(self):
        """Test custom values."""
        signal = SignalData(
            quality={"rsrq": 10, "rsrp": 20},
            band="BAND 7",
            cell="123:45"
        )
        self.assertEqual(signal.quality, {"rsrq": 10, "rsrp": 20})
        self.assertEqual(signal.band, "BAND 7")
        self.assertEqual(signal.cell, "123:45")


class TestTelemetryContext(unittest.TestCase):
    """Test TelemetryContext class."""

    def setUp(self):
        """Set up test fixtures."""
        self.context = TelemetryContext()

    def test_initial_state(self):
        """Test initial state of context."""
        services = self.context.get_services()
        self.assertFalse(services.video)
        self.assertFalse(services.reverse_shell)
        self.assertFalse(services.debug)

        gst = self.context.get_gst()
        self.assertFalse(gst.recording)

        vc = self.context.get_videocore()
        self.assertEqual(vc.current, 0)
        self.assertEqual(vc.history, 0)

        battery = self.context.get_battery()
        self.assertEqual(battery.icon, 0)
        self.assertEqual(battery.voltage, "0.00V")

        signal = self.context.get_signal()
        self.assertEqual(signal.quality, {"rsrq": -1, "rsrp": -1})
        self.assertEqual(signal.band, "BAND ?")

    def test_update_services(self):
        """Test updating service flags."""
        self.context.update_services(0b00000001)
        services = self.context.get_services()
        self.assertTrue(services.video)
        self.assertFalse(services.reverse_shell)
        self.assertFalse(services.debug)

        self.context.update_services(0b00000111)
        services = self.context.get_services()
        self.assertTrue(services.video)
        self.assertTrue(services.reverse_shell)
        self.assertTrue(services.debug)

    def test_update_gst(self):
        """Test updating GST flags."""
        self.context.update_gst(0b00000000)
        gst = self.context.get_gst()
        self.assertFalse(gst.recording)

        self.context.update_gst(0b00000001)
        gst = self.context.get_gst()
        self.assertTrue(gst.recording)

    def test_update_videocore(self):
        """Test updating VideoCore flags."""
        self.context.update_videocore(0b10100101)
        vc = self.context.get_videocore()
        self.assertEqual(vc.current, 0x05)
        self.assertEqual(vc.history, 0x0A)

    def test_update_signal_quality(self):
        """Test updating signal quality."""
        self.context.update_signal_quality(10, 20)
        signal = self.context.get_signal()
        self.assertEqual(signal.quality, {"rsrq": 10, "rsrp": 20})

    def test_update_signal_band(self):
        """Test updating signal band."""
        self.context.update_signal_band("BAND 7")
        signal = self.context.get_signal()
        self.assertEqual(signal.band, "BAND 7")

    def test_update_signal_cell(self):
        """Test updating signal cell."""
        self.context.update_signal_cell("123:45")
        signal = self.context.get_signal()
        self.assertEqual(signal.cell, "123:45")

    def test_update_battery(self):
        """Test updating battery data."""
        self.context.update_battery(
            icon=75,
            voltage="12.34V",
            average_voltage="12.30V",
            percent="75%",
            warning=True
        )
        battery = self.context.get_battery()
        self.assertEqual(battery.icon, 75)
        self.assertEqual(battery.voltage, "12.34V")
        self.assertEqual(battery.average_voltage, "12.30V")
        self.assertEqual(battery.percent, "75%")
        self.assertTrue(battery.warning)

    def test_reset(self):
        """Test resetting all telemetry data."""
        # Set some values
        self.context.update_services(0b00000111)
        self.context.update_gst(0b00000001)
        self.context.update_battery(75, "12.34V", "12.30V", "75%", True)
        self.context.update_signal_band("BAND 7")

        # Reset
        self.context.reset()

        # Verify all back to defaults
        services = self.context.get_services()
        self.assertFalse(services.video)
        self.assertFalse(services.reverse_shell)
        self.assertFalse(services.debug)

        gst = self.context.get_gst()
        self.assertFalse(gst.recording)

        battery = self.context.get_battery()
        self.assertEqual(battery.icon, 0)
        self.assertEqual(battery.voltage, "0.00V")

        signal = self.context.get_signal()
        self.assertEqual(signal.band, "BAND ?")

    def test_get_returns_copy(self):
        """Test that get methods return copies, not references."""
        self.context.update_services(0b00000001)
        services1 = self.context.get_services()
        services2 = self.context.get_services()

        # Should be different objects
        self.assertIsNot(services1, services2)

        # But same values
        self.assertEqual(services1.video, services2.video)

    def test_signal_quality_dict_is_copy(self):
        """Test that signal quality dict is a copy."""
        self.context.update_signal_quality(10, 20)
        signal = self.context.get_signal()

        # Modify the returned dict
        signal.quality["rsrq"] = 999

        # Original should be unchanged
        signal2 = self.context.get_signal()
        self.assertEqual(signal2.quality["rsrq"], 10)

    def test_thread_safety_concurrent_updates(self):
        """Test thread safety with concurrent updates."""
        def update_services():
            for _ in range(100):
                self.context.update_services(0b00000001)
                time.sleep(0.001)

        def update_gst():
            for _ in range(100):
                self.context.update_gst(0b00000001)
                time.sleep(0.001)

        def update_battery():
            for i in range(100):
                self.context.update_battery(i, f"{i}.00V", f"{i}.00V", f"{i}%", False)
                time.sleep(0.001)

        # Start multiple threads
        threads = [
            threading.Thread(target=update_services),
            threading.Thread(target=update_gst),
            threading.Thread(target=update_battery)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should complete without errors (no assertion needed, just shouldn't crash)
        services = self.context.get_services()
        self.assertIsInstance(services, ServiceFlags)

    def test_thread_safety_concurrent_reads_writes(self):
        """Test thread safety with concurrent reads and writes."""
        results = []

        def reader():
            for _ in range(50):
                services = self.context.get_services()
                gst = self.context.get_gst()
                battery = self.context.get_battery()
                results.append((services, gst, battery))
                time.sleep(0.001)

        def writer():
            for i in range(50):
                self.context.update_services(i % 2)
                self.context.update_gst(i % 2)
                self.context.update_battery(i, f"{i}.00V", f"{i}.00V", f"{i}%", False)
                time.sleep(0.001)

        # Start reader and writer threads
        reader_thread = threading.Thread(target=reader)
        writer_thread = threading.Thread(target=writer)

        reader_thread.start()
        writer_thread.start()

        reader_thread.join()
        writer_thread.join()

        # Should have collected results without errors
        self.assertEqual(len(results), 50)
        for services, gst, battery in results:
            self.assertIsInstance(services, ServiceFlags)
            self.assertIsInstance(gst, GstFlags)
            self.assertIsInstance(battery, BatteryData)


class TestTelemetryContextIntegration(unittest.TestCase):
    """Integration tests simulating real usage."""

    def test_simulated_telemetry_update(self):
        """Test simulating a complete telemetry update."""
        context = TelemetryContext()

        # Simulate receiving telemetry message
        context.update_services(0b00000001)  # video service active
        context.update_gst(0b00000001)       # recording active
        context.update_videocore(0b10100101)
        context.update_signal_quality(-10, -80)
        context.update_signal_band("BAND 7")
        context.update_signal_cell("123:45")
        context.update_battery(75, "12.34V", "12.30V", "75%", False)

        # Verify all updates
        services = context.get_services()
        self.assertTrue(services.video)

        gst = context.get_gst()
        self.assertTrue(gst.recording)

        vc = context.get_videocore()
        self.assertEqual(vc.current, 0x05)
        self.assertEqual(vc.history, 0x0A)

        signal = context.get_signal()
        self.assertEqual(signal.quality, {"rsrq": -10, "rsrp": -80})
        self.assertEqual(signal.band, "BAND 7")
        self.assertEqual(signal.cell, "123:45")

        battery = context.get_battery()
        self.assertEqual(battery.icon, 75)
        self.assertEqual(battery.voltage, "12.34V")
        self.assertEqual(battery.percent, "75%")
        self.assertFalse(battery.warning)

    def test_simulated_osd_and_menu_access(self):
        """Test simulating OSD updating and Menu reading."""
        context = TelemetryContext()

        # Simulate OSD updating from telemetry
        def osd_thread():
            for i in range(10):
                context.update_services(0b00000001 if i % 2 == 0 else 0b00000000)
                context.update_gst(0b00000001 if i % 3 == 0 else 0b00000000)
                time.sleep(0.01)

        # Simulate Menu/StreamerTab reading
        menu_reads = []

        def menu_thread():
            for _ in range(10):
                services = context.get_services()
                gst = context.get_gst()
                menu_reads.append((services.video, gst.recording))
                time.sleep(0.01)

        osd = threading.Thread(target=osd_thread)
        menu = threading.Thread(target=menu_thread)

        osd.start()
        menu.start()

        osd.join()
        menu.join()

        # Should have collected 10 reads
        self.assertEqual(len(menu_reads), 10)

        # All reads should be valid booleans
        for video, recording in menu_reads:
            self.assertIsInstance(video, bool)
            self.assertIsInstance(recording, bool)


if __name__ == '__main__':
    unittest.main()

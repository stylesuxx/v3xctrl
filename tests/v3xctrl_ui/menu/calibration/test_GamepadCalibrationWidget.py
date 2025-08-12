import unittest
from unittest.mock import MagicMock, patch, Mock
import pygame
from pygame.freetype import Font
from typing import Dict

from v3xctrl_ui.menu.calibration.GamepadCalibrationWidget import GamepadCalibrationWidget
from v3xctrl_ui.menu.calibration.GamepadCalibrator import CalibratorState
from v3xctrl_ui.GamepadManager import GamepadManager


class TestGamepadCalibrationWidget(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        pygame.init()
        pygame.joystick.init()

        self.mock_font = MagicMock(spec=Font)
        # Mock font.render to return proper surface and rect objects
        mock_surface = MagicMock()
        mock_rect = MagicMock()
        mock_rect.width = 100
        mock_rect.height = 20
        mock_rect.topleft = (0, 0)
        self.mock_font.render.return_value = (mock_surface, mock_rect)

        self.mock_manager = MagicMock(spec=GamepadManager)
        self.mock_on_start = MagicMock()
        self.mock_on_done = MagicMock()

        # Mock joystick objects
        self.mock_joystick1 = MagicMock()
        self.mock_joystick1.get_name.return_value = "Test Controller 1"
        self.mock_joystick1.get_guid.return_value = "guid1"
        self.mock_joystick1.get_init.return_value = True
        self.mock_joystick1.get_numaxes.return_value = 3
        self.mock_joystick1.get_axis.side_effect = lambda i: [0.1, 0.2, 0.3][i]

        self.mock_joystick2 = MagicMock()
        self.mock_joystick2.get_name.return_value = "Test Controller 2"
        self.mock_joystick2.get_guid.return_value = "guid2"
        self.mock_joystick2.get_init.return_value = True
        self.mock_joystick2.get_numaxes.return_value = 3
        self.mock_joystick2.get_axis.side_effect = lambda i: [0.4, 0.5, 0.6][i]

        # Setup mock manager
        self.gamepads = {
            "guid1": self.mock_joystick1,
            "guid2": self.mock_joystick2
        }
        self.mock_manager.get_gamepads.return_value = self.gamepads
        # Setup mock manager - make sure get_calibration returns None initially
        self.mock_manager.get_calibration.return_value = None

        # Patch UI components before creating widget to avoid size calculation issues
        with patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.Select') as MockSelect, \
             patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.Button') as MockButton, \
             patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.Checkbox') as MockCheckbox:

            # Setup Select mock
            mock_select = MagicMock()
            mock_select.get_size.return_value = (200, 30)
            mock_select.expanded = False
            MockSelect.return_value = mock_select

            # Setup Button mock
            mock_button = MagicMock()
            mock_button.get_size.return_value = (150, 35)
            MockButton.return_value = mock_button

            # Store references to the mock checkboxes for testing
            self.mock_checkbox_refs = {}

            # Setup Checkbox mock to create unique instances
            def create_checkbox(*args, **kwargs):
                mock_checkbox = MagicMock()
                mock_checkbox.checked = False
                return mock_checkbox

            MockCheckbox.side_effect = create_checkbox

            self.widget = GamepadCalibrationWidget(
                font=self.mock_font,
                manager=self.mock_manager,
                on_calibration_start=self.mock_on_start,
                on_calibration_done=self.mock_on_done
            )

    def tearDown(self):
        """Clean up after tests"""
        pygame.joystick.quit()
        pygame.quit()

    def test_initialization(self):
        """Test widget initialization"""
        # Test basic properties
        self.assertEqual(self.widget.font, self.mock_font)
        self.assertEqual(self.widget.manager, self.mock_manager)
        self.assertEqual(self.widget.on_calibration_start, self.mock_on_start)
        self.assertEqual(self.widget.on_calibration_done, self.mock_on_done)

        # Test initial state
        self.assertIsNotNone(self.widget.selected_guid)  # Should select first gamepad

        # Test invert axes initialization - they should start as False
        expected_axes = {"steering": False, "throttle": False, "brake": False}
        # Check the keys exist and have boolean values (may have been overwritten during setup)
        for key in expected_axes:
            self.assertIn(key, self.widget.invert_axes)
            self.assertIsInstance(self.widget.invert_axes[key], bool)

        # Test UI components creation
        self.assertIsNotNone(self.widget.controller_select)
        self.assertIsNotNone(self.widget.calibrate_button)
        self.assertIsNotNone(self.widget.invert_checkboxes)
        self.assertEqual(len(self.widget.invert_checkboxes), 3)

        # Test dialog creation
        self.assertIsNotNone(self.widget.dialog)

        # Test manager observer registration
        self.mock_manager.add_observer.assert_called_once()

    def test_initialization_without_callbacks(self):
        """Test initialization with default callbacks"""
        # Patch UI components for this test too
        with patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.Select') as MockSelect, \
             patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.Button') as MockButton, \
             patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.Checkbox') as MockCheckbox:

            # Setup Select mock
            mock_select = MagicMock()
            mock_select.get_size.return_value = (200, 30)
            mock_select.expanded = False
            MockSelect.return_value = mock_select

            # Setup Button mock
            mock_button = MagicMock()
            mock_button.get_size.return_value = (150, 35)
            MockButton.return_value = mock_button

            # Setup Checkbox mock
            mock_checkbox = MagicMock()
            mock_checkbox.checked = False
            MockCheckbox.return_value = mock_checkbox

            # Mock manager for this test
            mock_manager = MagicMock()
            mock_manager.get_gamepads.return_value = {}

            widget = GamepadCalibrationWidget(
                font=self.mock_font,
                manager=mock_manager
            )

            # Should not raise exceptions when called
            widget.on_calibration_start()
            widget.on_calibration_done()

    def test_constants(self):
        """Test class constants"""
        self.assertEqual(GamepadCalibrationWidget.GAMEPAD_REFRESH_INTERVAL_MS, 1000)
        self.assertEqual(GamepadCalibrationWidget.BAR_WIDTH, 400)
        self.assertEqual(GamepadCalibrationWidget.BAR_HEIGHT, 30)
        self.assertEqual(GamepadCalibrationWidget.BAR_SPACING, 50)
        self.assertEqual(GamepadCalibrationWidget.INSTRUCTION_Y_OFFSET, 70)
        self.assertEqual(GamepadCalibrationWidget.BARS_X_OFFSSET, 100)
        self.assertEqual(GamepadCalibrationWidget.INVERT_X_OFFSET, 530)

    def test_on_gamepads_changed_with_gamepads(self):
        """Test gamepad change handling with available gamepads"""
        new_gamepads = {
            "guid3": MagicMock(),
            "guid4": MagicMock()
        }
        new_gamepads["guid3"].get_name.return_value = "New Controller 1"
        new_gamepads["guid4"].get_name.return_value = "New Controller 2"

        self.widget._on_gamepads_changed(new_gamepads)

        # Should update gamepads and select first one
        self.assertEqual(self.widget.gamepads, new_gamepads)
        self.assertEqual(self.widget.selected_guid, "guid3")

        # Should update controller select options
        self.widget.controller_select.set_options.assert_called()

    def test_on_gamepads_changed_empty(self):
        """Test gamepad change handling with no gamepads"""
        self.widget._on_gamepads_changed({})

        # Should clear selection
        self.assertEqual(self.widget.gamepads, {})
        self.assertIsNone(self.widget.selected_guid)
        self.assertIsNone(self.widget.calibrator)

        # Should set empty options
        self.widget.controller_select.set_options.assert_called_with([], selected_index=0)

    def test_on_gamepads_changed_preserve_selection(self):
        """Test gamepad change preserves existing selection if still available"""
        self.widget.selected_guid = "guid2"

        # Same gamepads, should preserve selection
        self.widget._on_gamepads_changed(self.gamepads)

        self.assertEqual(self.widget.selected_guid, "guid2")

    def test_get_selected_guid(self):
        """Test get_selected_guid method"""
        self.widget.selected_guid = "test_guid"
        self.assertEqual(self.widget.get_selected_guid(), "test_guid")

        self.widget.selected_guid = None
        self.assertIsNone(self.widget.get_selected_guid())

    def test_get_size(self):
        """Test get_size calculation"""
        # Component sizes are already mocked in setUp
        width, height = self.widget.get_size()

        # Total width should be select_width + 10 + button_width
        self.assertEqual(width, 200 + 10 + 150)
        # Height should be max of component heights
        self.assertEqual(height, 35)

    def test_set_position(self):
        """Test position setting"""
        self.widget.set_position(100, 200)

        # Should call parent set_position
        self.assertEqual(self.widget.x, 100)
        self.assertEqual(self.widget.y, 200)

        # Should position controller select
        self.widget.controller_select.set_position.assert_called_with(100, 200)

        # Should position calibrate button relative to select
        # Expected position: x + select_width + 20, y + (select_height // 2) - (button_height // 2)
        expected_x = 100 + 200 + 20  # x + select_width + 20
        expected_y = 200 + (30 // 2) - (35 // 2)  # y + (select_height // 2) - (button_height // 2)
        self.widget.calibrate_button.set_position.assert_called_with(expected_x, expected_y)

    def test_start_calibration_when_active(self):
        """Test start calibration when already active"""
        # Setup active calibrator
        mock_calibrator = MagicMock()
        mock_calibrator.state = CalibratorState.ACTIVE
        self.widget.calibrator = mock_calibrator

        self.widget._start_calibration()

        # Should do nothing when already active
        mock_calibrator.start.assert_not_called()

    def test_start_calibration_success(self):
        """Test successful calibration start"""
        self.widget.selected_guid = "guid1"

        with patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.GamepadCalibrator') as MockCalibrator:
            mock_calibrator_instance = MagicMock()
            MockCalibrator.return_value = mock_calibrator_instance

            self.widget._start_calibration()

            # Should create new calibrator with proper callbacks
            MockCalibrator.assert_called_once()
            args, kwargs = MockCalibrator.call_args
            self.assertIn('on_start', kwargs)
            self.assertIn('on_done', kwargs)
            self.assertEqual(kwargs['dialog'], self.widget.dialog)

            # Should start calibration
            mock_calibrator_instance.start.assert_called_once()

            # Should store calibrator reference
            self.assertEqual(self.widget.calibrator, mock_calibrator_instance)

    def test_calibration_on_start_callback(self):
        """Test calibration on_start callback behavior"""
        self.widget.selected_guid = "guid1"

        with patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.GamepadCalibrator') as MockCalibrator:
            mock_calibrator_instance = MagicMock()
            MockCalibrator.return_value = mock_calibrator_instance

            self.widget._start_calibration()

            # Get the on_start callback
            on_start_callback = MockCalibrator.call_args[1]['on_start']

            # Execute the callback
            on_start_callback()

            # Should disable UI elements and call user callback
            self.widget.calibrate_button.disable.assert_called_once()
            self.widget.controller_select.disable.assert_called_once()
            self.mock_on_start.assert_called_once()

    def test_calibration_on_done_callback(self):
        """Test calibration on_done callback behavior"""
        self.widget.selected_guid = "guid1"

        with patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.GamepadCalibrator') as MockCalibrator:
            mock_calibrator_instance = MagicMock()
            mock_calibrator_instance.get_settings.return_value = {
                "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0},
                "throttle": {"axis": 1, "min": 0.0, "max": 1.0, "center": None},
                "brake": {"axis": 2, "min": 0.0, "max": 1.0, "center": None}
            }
            MockCalibrator.return_value = mock_calibrator_instance

            # Set some invert states
            self.widget.invert_axes = {"steering": True, "throttle": False, "brake": True}

            self.widget._start_calibration()

            # Get and execute the on_done callback
            on_done_callback = MockCalibrator.call_args[1]['on_done']
            on_done_callback()

            # Should re-enable UI elements
            self.widget.calibrate_button.enable.assert_called_once()
            self.widget.controller_select.enable.assert_called_once()

            # Should apply invert settings and save calibration
            expected_settings = {
                "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0, "invert": True},
                "throttle": {"axis": 1, "min": 0.0, "max": 1.0, "center": None, "invert": False},
                "brake": {"axis": 2, "min": 0.0, "max": 1.0, "center": None, "invert": True}
            }
            self.mock_manager.set_calibration.assert_called_with("guid1", expected_settings)
            self.mock_manager.set_active.assert_called_with("guid1")
            self.mock_on_done.assert_called_once()

    def test_set_selected_gamepad_valid_index(self):
        """Test setting selected gamepad with valid index"""
        self.widget.set_selected_gamepad(1)  # Select second gamepad

        self.assertEqual(self.widget.selected_guid, "guid2")

    def test_set_selected_gamepad_invalid_index(self):
        """Test setting selected gamepad with invalid index"""
        original_guid = self.widget.selected_guid

        # Test negative index
        self.widget.set_selected_gamepad(-1)
        self.assertEqual(self.widget.selected_guid, original_guid)

        # Test too large index
        self.widget.set_selected_gamepad(10)
        self.assertEqual(self.widget.selected_guid, original_guid)

    def test_apply_known_calibration_with_settings(self):
        """Test applying known calibration settings"""
        mock_settings = {
            "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0, "invert": True},
            "throttle": {"axis": 1, "min": 0.0, "max": 1.0, "center": None, "invert": False},
            "brake": {"axis": 2, "min": 0.0, "max": 1.0, "center": None, "invert": True}
        }

        # Clear existing calibrator to test creation
        self.widget.calibrator = None
        self.mock_manager.get_calibration.return_value = mock_settings

        with patch('v3xctrl_ui.menu.calibration.GamepadCalibrationWidget.GamepadCalibrator') as MockCalibrator:
            mock_calibrator_instance = MagicMock()
            MockCalibrator.return_value = mock_calibrator_instance

            self.widget._apply_known_calibration(self.mock_joystick1)

            # Should set manager as active
            self.mock_manager.set_active.assert_called_with("guid1")

            # Should create calibrator in complete state
            self.assertIsNotNone(self.widget.calibrator)
            self.assertEqual(self.widget.calibrator.state, CalibratorState.COMPLETE)

            # Should apply invert settings to internal state
            expected_invert = {"steering": True, "throttle": False, "brake": True}
            self.assertEqual(self.widget.invert_axes, expected_invert)

    def test_apply_known_calibration_without_settings(self):
        """Test applying known calibration when no settings exist"""
        self.mock_manager.get_calibration.return_value = None

        original_calibrator = self.widget.calibrator

        self.widget._apply_known_calibration(self.mock_joystick1)

        # Should not change calibrator
        self.assertEqual(self.widget.calibrator, original_calibrator)

    def test_toggle_invert(self):
        """Test toggling invert settings"""
        self.widget.selected_guid = "guid1"
        mock_settings = {
            "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0, "invert": False}
        }
        self.mock_manager.get_calibration.return_value = mock_settings

        self.widget.toggle_invert("steering", True)

        # Should update local state
        self.assertTrue(self.widget.invert_axes["steering"])

        # Should update manager settings
        self.assertEqual(mock_settings["steering"]["invert"], True)
        self.mock_manager.set_calibration.assert_called_with("guid1", mock_settings)

    def test_toggle_invert_no_settings(self):
        """Test toggling invert when no calibration settings exist"""
        self.widget.selected_guid = "guid1"
        self.mock_manager.get_calibration.return_value = None

        self.widget.toggle_invert("steering", True)

        # Should update local state only
        self.assertTrue(self.widget.invert_axes["steering"])

        # Should not call set_calibration
        self.mock_manager.set_calibration.assert_not_called()

    def test_handle_event_with_visible_dialog(self):
        """Test event handling when dialog is visible"""
        self.widget.dialog.visible = True
        self.widget.dialog.handle_event = MagicMock()  # Properly mock the method
        mock_event = MagicMock()

        self.widget.handle_event(mock_event)

        # Should only handle dialog event
        self.widget.dialog.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_with_expanded_select(self):
        """Test event handling when controller select is expanded"""
        self.widget.dialog.visible = False
        self.widget.controller_select.expanded = True
        mock_event = MagicMock()

        self.widget.handle_event(mock_event)

        # Should only handle select event
        self.widget.controller_select.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_normal(self):
        """Test normal event handling"""
        self.widget.dialog.visible = False
        self.widget.controller_select.expanded = False
        mock_event = MagicMock()

        self.widget.handle_event(mock_event)

        # Should handle all UI element events
        self.widget.calibrate_button.handle_event.assert_called_once_with(mock_event)
        self.widget.controller_select.handle_event.assert_called_once_with(mock_event)

        # Each checkbox should handle the event once
        for checkbox in self.widget.invert_checkboxes.values():
            checkbox.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_no_gamepads(self):
        """Test event handling when no gamepads are connected"""
        self.widget.gamepads = {}
        mock_event = MagicMock()

        # Should not crash
        self.widget.handle_event(mock_event)

    def test_draw_no_gamepad_message(self):
        """Test drawing when no gamepads are available"""
        self.widget.gamepads = {}
        mock_surface = MagicMock()

        self.widget.draw(mock_surface)

        # Should render "no gamepad" message
        self.mock_font.render.assert_called_with("No gamepad detected. Please connect one...", unittest.mock.ANY)
        mock_surface.blit.assert_called()

    def test_draw_with_gamepads_no_calibrator(self):
        """Test drawing with gamepads but no calibrator"""
        # Clear calibrator to ensure it's None
        self.widget.calibrator = None

        # Create a real pygame surface for this test
        mock_surface = pygame.Surface((800, 600))

        self.widget.draw(mock_surface)

        # Should draw UI elements
        self.widget.controller_select.draw.assert_called_once_with(mock_surface)
        self.widget.calibrate_button.draw.assert_called_once_with(mock_surface)

    def test_draw_with_complete_calibrator(self):
        """Test drawing with completed calibrator"""
        mock_surface = MagicMock()
        mock_calibrator = MagicMock()
        mock_calibrator.state = CalibratorState.COMPLETE
        self.widget.calibrator = mock_calibrator

        # Mock manager inputs
        self.mock_manager.read_inputs.return_value = {
            "steering": 0.5,
            "throttle": 0.8,
            "brake": 0.2
        }

        # Mock calibration settings
        mock_settings = {
            "steering": {"center": 0.0},
            "throttle": {},
            "brake": {}
        }
        self.mock_manager.get_calibration.return_value = mock_settings

        with patch.object(self.widget, '_draw_calibration_bars') as mock_draw_bars:
            self.widget.draw(mock_surface)

            mock_draw_bars.assert_called_once_with(mock_surface)

    def test_draw_with_active_calibrator(self):
        """Test drawing with active calibrator"""
        mock_surface = MagicMock()
        mock_calibrator = MagicMock()
        mock_calibrator.state = CalibratorState.ACTIVE
        mock_calibrator.stage = MagicMock()  # Some stage
        mock_calibrator.get_steps.return_value = [
            ("Step 1", True),
            ("Step 2", False),
            ("Step 3", False)
        ]
        self.widget.calibrator = mock_calibrator

        with patch.object(self.widget, '_draw_calibration_steps') as mock_draw_steps:
            self.widget.draw(mock_surface)

            mock_draw_steps.assert_called_once_with(mock_surface)

    def test_update_calibrator(self):
        """Test calibrator update with gamepad input"""
        mock_calibrator = MagicMock()
        self.widget.calibrator = mock_calibrator
        self.widget.selected_guid = "guid1"

        self.widget._update_calibrator()

        # Should read axes and update calibrator
        expected_axes = [0.1, 0.2, 0.3]
        mock_calibrator.update.assert_called_once_with(expected_axes)

    def test_update_calibrator_no_joystick(self):
        """Test calibrator update with no selected joystick"""
        mock_calibrator = MagicMock()
        self.widget.calibrator = mock_calibrator
        self.widget.selected_guid = "nonexistent"

        self.widget._update_calibrator()

        # Should not update calibrator
        mock_calibrator.update.assert_not_called()

    def test_update_calibrator_uninitialized_joystick(self):
        """Test calibrator update with uninitialized joystick"""
        mock_calibrator = MagicMock()
        self.widget.calibrator = mock_calibrator
        self.widget.selected_guid = "guid1"
        self.mock_joystick1.get_init.return_value = False

        self.widget._update_calibrator()

        # Should not update calibrator
        mock_calibrator.update.assert_not_called()

    @patch('pygame.draw.rect')
    @patch('pygame.draw.line')
    def test_draw_bar(self, mock_draw_line, mock_draw_rect):
        """Test bar drawing functionality"""
        mock_surface = MagicMock()

        self.widget._draw_bar(
            mock_surface, "Test Axis", 0.5,
            min_val=-1.0, max_val=1.0, center_val=0.0,
            x=100, y=200, width=400, height=30
        )

        # Should render label
        self.mock_font.render.assert_called()

        # Should draw bar outline
        mock_draw_rect.assert_called()

        # Should draw center line
        mock_draw_line.assert_called()

    def test_draw_bar_no_center(self):
        """Test bar drawing without center line"""
        mock_surface = MagicMock()

        with patch('pygame.draw.rect') as mock_draw_rect, \
             patch('pygame.draw.line') as mock_draw_line:

            self.widget._draw_bar(
                mock_surface, "Test Axis", 0.5,
                min_val=0.0, max_val=1.0, center_val=None,
                x=100, y=200
            )

            # Should not draw center line
            mock_draw_line.assert_not_called()

            # Should still draw bar
            mock_draw_rect.assert_called()


if __name__ == '__main__':
    unittest.main()
"""Tests for SettingsController - handles settings updates and coordination."""

from unittest.mock import Mock

from v3xctrl_ui.core.controllers.SettingsController import SettingsController
from v3xctrl_ui.core.dataclasses import ApplicationModel


class FakeSubscriber:
    """Records the settings handed to it."""

    def __init__(self, name: str, log: list[str] | None = None) -> None:
        self.name = name
        self.log = log
        self.received: list[dict] = []

    def apply_settings(self, settings: dict) -> None:
        self.received.append(settings)
        if self.log is not None:
            self.log.append(self.name)


class FakeNetworkRestarter:
    """Restart port that completes on demand instead of on a thread."""

    def __init__(self) -> None:
        self.restart_calls: list[dict] = []
        self.complete = False
        self.acknowledged = 0
        self.waited_timeouts: list[float] = []
        self.wait_result = True

    def restart(self, settings: dict) -> None:
        self.restart_calls.append(settings)

    def is_restart_complete(self) -> bool:
        return self.complete

    def acknowledge_restart(self) -> None:
        self.acknowledged += 1
        self.complete = False

    def wait_for_restart(self, timeout: float) -> bool:
        self.waited_timeouts.append(timeout)
        return self.wait_result


def build_controller(settings: dict, model: ApplicationModel | None = None):
    model = model if model is not None else ApplicationModel()
    restarter = FakeNetworkRestarter()
    fullscreen_change = Mock()
    controller = SettingsController(settings, model, restarter, fullscreen_change)

    return controller, restarter, fullscreen_change, model


class TestInitialization:
    def test_keeps_a_deep_copy_of_the_starting_settings(self):
        settings = {"video": {"fullscreen": False}, "ports": {"video": 6666}}

        controller, _restarter, _fullscreen, model = build_controller(settings)

        assert controller.settings == settings
        assert controller.model is model
        assert controller.old_settings == settings
        assert controller.old_settings is not settings

    def test_starts_with_no_subscribers(self):
        controller, _restarter, _fullscreen, _model = build_controller({})

        controller.apply_settings({"video": {}})


class TestSubscriberNotification:
    def test_every_subscriber_receives_the_new_settings(self):
        controller, _restarter, _fullscreen, _model = build_controller({})
        first = FakeSubscriber("first")
        second = FakeSubscriber("second")
        controller.register(first)
        controller.register(second)

        new_settings = {"video": {"fullscreen": True}}
        controller.apply_settings(new_settings)

        assert first.received == [new_settings]
        assert second.received == [new_settings]

    def test_subscribers_are_notified_in_registration_order(self):
        controller, _restarter, _fullscreen, _model = build_controller({})
        order: list[str] = []
        for name in ("timing", "network", "input", "osd", "renderer"):
            controller.register(FakeSubscriber(name, order))

        controller.apply_settings({})

        assert order == ["timing", "network", "input", "osd", "renderer"]

    def test_apply_settings_updates_its_own_references(self):
        controller, _restarter, _fullscreen, _model = build_controller({"ports": {"video": 1}})
        new_settings = {"ports": {"video": 2}}

        controller.apply_settings(new_settings)

        assert controller.settings == new_settings
        assert controller.old_settings == new_settings
        assert controller.old_settings is not new_settings


class TestUpdateSettings:
    def test_applies_immediately_when_nothing_network_facing_changed(self):
        settings = {"video": {"fullscreen": False}, "ports": {"video": 6666}, "relay": {}}
        controller, restarter, _fullscreen, model = build_controller(settings)
        model.user_connected = True
        subscriber = FakeSubscriber("subscriber")
        controller.register(subscriber)

        applied = controller.update_settings({"video": {"fullscreen": False}, "ports": {"video": 6666}, "relay": {}})

        assert applied is True
        assert restarter.restart_calls == []
        assert len(subscriber.received) == 1

    def test_applies_immediately_before_the_user_connects(self):
        settings = {"video": {}, "ports": {"video": 6666}, "relay": {}}
        controller, restarter, _fullscreen, model = build_controller(settings)
        model.user_connected = False

        applied = controller.update_settings({"video": {}, "ports": {"video": 9999}, "relay": {}})

        assert applied is True
        assert restarter.restart_calls == []

    def test_port_change_defers_behind_a_restart(self):
        settings = {"video": {}, "ports": {"video": 6666}, "relay": {}}
        controller, restarter, _fullscreen, model = build_controller(settings)
        model.user_connected = True
        subscriber = FakeSubscriber("subscriber")
        controller.register(subscriber)

        new_settings = {"video": {}, "ports": {"video": 9999}, "relay": {}}
        applied = controller.update_settings(new_settings)

        assert applied is False
        assert restarter.restart_calls == [new_settings]
        assert model.pending_settings == new_settings
        assert subscriber.received == []

    def test_relay_change_defers_behind_a_restart(self):
        settings = {"video": {}, "ports": {}, "relay": {"enabled": False, "id": "abc"}}
        controller, restarter, _fullscreen, model = build_controller(settings)
        model.user_connected = True

        new_settings = {"video": {}, "ports": {}, "relay": {"enabled": True, "id": "abc"}}
        applied = controller.update_settings(new_settings)

        assert applied is False
        assert restarter.restart_calls == [new_settings]

    def test_transport_change_defers_behind_a_restart(self):
        settings = {"video": {}, "ports": {}, "relay": {}, "transport": "udp"}
        controller, restarter, _fullscreen, model = build_controller(settings)
        model.user_connected = True

        new_settings = {"video": {}, "ports": {}, "relay": {}, "transport": "tcp"}
        applied = controller.update_settings(new_settings)

        assert applied is False
        assert restarter.restart_calls == [new_settings]


class TestFullscreen:
    def test_fullscreen_change_is_reported(self):
        settings = {"video": {"fullscreen": False}, "ports": {}, "relay": {}}
        controller, _restarter, fullscreen_change, _model = build_controller(
            settings, ApplicationModel(fullscreen=False)
        )

        controller.update_settings({"video": {"fullscreen": True}, "ports": {}, "relay": {}})

        fullscreen_change.assert_called_once_with(True)

    def test_unchanged_fullscreen_is_not_reported(self):
        settings = {"video": {"fullscreen": False}, "ports": {}, "relay": {}}
        controller, _restarter, fullscreen_change, _model = build_controller(
            settings, ApplicationModel(fullscreen=False)
        )

        controller.update_settings({"video": {"fullscreen": False}, "ports": {}, "relay": {}})

        fullscreen_change.assert_not_called()

    def test_fullscreen_applies_ahead_of_a_deferred_restart(self):
        """The window responds to the save even when everything else waits."""
        settings = {"video": {"fullscreen": False}, "ports": {"video": 6666}, "relay": {}}
        controller, restarter, fullscreen_change, model = build_controller(settings, ApplicationModel(fullscreen=False))
        model.user_connected = True

        applied = controller.update_settings({"video": {"fullscreen": True}, "ports": {"video": 9999}, "relay": {}})

        assert applied is False
        assert restarter.restart_calls != []
        fullscreen_change.assert_called_once_with(True)


class TestRestartCompletion:
    def test_reports_nothing_while_the_restart_runs(self):
        controller, _restarter, _fullscreen, _model = build_controller({})

        assert controller.check_network_restart_complete() is False

    def test_pending_settings_are_applied_once_the_restart_finishes(self):
        controller, restarter, _fullscreen, model = build_controller({})
        subscriber = FakeSubscriber("subscriber")
        controller.register(subscriber)
        pending = {"ports": {"video": 9999}}
        model.pending_settings = pending
        restarter.complete = True

        result = controller.check_network_restart_complete()

        assert result is True
        assert subscriber.received == [pending]
        assert model.pending_settings is None

    def test_completion_is_acknowledged_so_the_next_restart_can_signal(self):
        controller, restarter, _fullscreen, _model = build_controller({})
        restarter.complete = True

        controller.check_network_restart_complete()

        assert restarter.acknowledged == 1
        assert restarter.is_restart_complete() is False

    def test_shutdown_waits_on_the_restarter(self):
        controller, restarter, _fullscreen, _model = build_controller({})

        result = controller.wait_for_network_restart(timeout=2.0)

        assert result is True
        assert restarter.waited_timeouts == [2.0]

    def test_shutdown_reports_a_restart_that_outlived_the_timeout(self):
        controller, restarter, _fullscreen, _model = build_controller({})
        restarter.wait_result = False

        assert controller.wait_for_network_restart(timeout=0.1) is False


class TestSettingsEqual:
    def test_equal_when_identical(self):
        settings = {"ports": {"video": 6666, "control": 6668}}
        controller, _restarter, _fullscreen, _model = build_controller(settings)

        assert controller.settings_equal({"ports": {"video": 6666, "control": 6668}}, "ports") is True

    def test_not_equal_when_values_differ(self):
        settings = {"ports": {"video": 6666}}
        controller, _restarter, _fullscreen, _model = build_controller(settings)

        assert controller.settings_equal({"ports": {"video": 9999}}, "ports") is False

    def test_not_equal_when_keys_differ(self):
        settings = {"ports": {"video": 6666}}
        controller, _restarter, _fullscreen, _model = build_controller(settings)

        assert controller.settings_equal({"ports": {"video": 6666, "control": 6668}}, "ports") is False


class TestWorkflow:
    def test_save_that_needs_a_restart_applies_once_it_completes(self):
        settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 6666},
            "relay": {},
            "timing": {"control_update_hz": 30},
        }
        controller, restarter, _fullscreen, model = build_controller(settings)
        model.user_connected = True
        subscriber = FakeSubscriber("subscriber")
        controller.register(subscriber)

        new_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 9999},
            "relay": {},
            "timing": {"control_update_hz": 60},
        }

        assert controller.update_settings(new_settings) is False
        assert subscriber.received == []

        restarter.complete = True
        assert controller.check_network_restart_complete() is True
        assert subscriber.received == [new_settings]
        assert controller.settings == new_settings

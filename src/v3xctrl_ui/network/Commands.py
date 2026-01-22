from v3xctrl_control.message import Command


class Commands:
    @staticmethod
    def service(name: str, action: str) -> Command:
        return Command("service", {"name": name, "action": action})

    @staticmethod
    def video_start() -> Command:
        return Commands.service("v3xctrl-video", "start")

    @staticmethod
    def video_stop() -> Command:
        return Commands.service("v3xctrl-video", "stop")

    @staticmethod
    def shell_start() -> Command:
        return Commands.service("v3xctrl-reverse-shell", "start")

    @staticmethod
    def shell_stop() -> Command:
        return Commands.service("v3xctrl-reverse-shell", "stop")

    @staticmethod
    def recording_start() -> Command:
        return Command("recording", {"action": "start"})

    @staticmethod
    def recording_stop() -> Command:
        return Command("recording", {"action": "stop"})

    @staticmethod
    def trim_increase() -> Command:
        return Command("trim", {"action": "increase"})

    @staticmethod
    def trim_decrease() -> Command:
        return Command("trim", {"action": "decrease"})

    @staticmethod
    def shutdown() -> Command:
        return Command("shutdown")

    @staticmethod
    def restart() -> Command:
        return Command("restart")

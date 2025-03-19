from src.rpi_4g_streamer import Message, Telemetry, Command, Control
from src.rpi_4g_streamer import Heartbeat, Syn, Ack


def test_telemetry_message():
    message = Telemetry({
      "key_1": "value_1",
      "key_2": "value_2",
    })
    data = message.to_bytes()
    new_message = Message.from_bytes(data)

    assert isinstance(new_message, Telemetry)
    assert message.timestamp == new_message.timestamp
    assert message.payload == new_message.payload


def test_command_message():
    message = Command('selfcheck')
    data = message.to_bytes()
    new_message = Message.from_bytes(data)

    assert isinstance(new_message, Command)
    assert message.timestamp == new_message.timestamp
    assert message.payload == new_message.payload


def test_control_message():
    message = Control({
      "key_1": "value_1",
      "key_2": "value_2",
    })
    data = message.to_bytes()
    new_message = Message.from_bytes(data)

    assert isinstance(new_message, Control)
    assert message.timestamp == new_message.timestamp
    assert message.payload == new_message.payload


def test_heartbeat_message():
    message = Heartbeat()
    data = message.to_bytes()
    new_message = Message.from_bytes(data)

    assert isinstance(new_message, Heartbeat)
    assert message.timestamp == new_message.timestamp
    assert message.payload == new_message.payload


def test_syn_message():
    message = Syn()
    data = message.to_bytes()
    new_message = Message.from_bytes(data)

    assert isinstance(new_message, Syn)
    assert message.timestamp == new_message.timestamp


def test_ack_message():
    message = Ack()
    data = message.to_bytes()
    new_message = Message.from_bytes(data)

    assert isinstance(new_message, Ack)
    assert message.timestamp == new_message.timestamp

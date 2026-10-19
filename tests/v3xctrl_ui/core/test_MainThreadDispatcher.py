import threading
import unittest

from v3xctrl_ui.core.MainThreadDispatcher import MainThreadDispatcher


class TestMainThreadDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = MainThreadDispatcher()

    def test_posted_callback_does_not_run_before_drain(self):
        calls = []

        self.dispatcher.post(calls.append, "first")

        self.assertEqual(calls, [])

    def test_drain_runs_posted_callbacks_in_order(self):
        calls = []

        self.dispatcher.post(calls.append, "first")
        self.dispatcher.post(calls.append, "second")
        self.dispatcher.drain()

        self.assertEqual(calls, ["first", "second"])

    def test_drain_passes_every_argument(self):
        received = []

        self.dispatcher.post(lambda *arguments: received.append(arguments), True, "message")
        self.dispatcher.drain()

        self.assertEqual(received, [(True, "message")])

    def test_drain_on_an_empty_dispatcher_does_nothing(self):
        self.dispatcher.drain()

    def test_second_drain_does_not_repeat_callbacks(self):
        calls = []

        self.dispatcher.post(calls.append, "once")
        self.dispatcher.drain()
        self.dispatcher.drain()

        self.assertEqual(calls, ["once"])

    def test_callback_posted_while_draining_runs_in_the_same_drain(self):
        calls = []

        def post_another() -> None:
            calls.append("first")
            self.dispatcher.post(calls.append, "second")

        self.dispatcher.post(post_another)
        self.dispatcher.drain()

        self.assertEqual(calls, ["first", "second"])

    def test_a_raising_callback_leaves_the_rest_queued(self):
        calls = []

        def fail() -> None:
            raise RuntimeError("callback failed")

        self.dispatcher.post(fail)
        self.dispatcher.post(calls.append, "after")

        with self.assertRaises(RuntimeError):
            self.dispatcher.drain()

        self.assertEqual(calls, [])

        self.dispatcher.drain()
        self.assertEqual(calls, ["after"])

    def test_callbacks_posted_from_another_thread_run_on_the_draining_thread(self):
        running_threads = []
        posted = threading.Event()

        def record() -> None:
            running_threads.append(threading.current_thread())

        def background() -> None:
            self.dispatcher.post(record)
            posted.set()

        worker = threading.Thread(target=background)
        worker.start()
        worker.join()
        self.assertTrue(posted.is_set())

        self.dispatcher.drain()

        self.assertEqual(running_threads, [threading.current_thread()])


if __name__ == "__main__":
    unittest.main()

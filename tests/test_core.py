import math
import threading
import time
import unittest

from f13_core import TapController, validate_frequency


class FakeKeyboard:
    def __init__(self, paused=False, fail=False):
        self.paused = paused
        self.fail = fail
        self.calls = 0
        self.tapped = threading.Event()

    def modifier_is_down(self):
        return self.paused

    def tap(self):
        if self.fail:
            raise RuntimeError("injected failure")
        self.calls += 1
        self.tapped.set()


def wait_for(predicate, timeout=1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class ControllerTests(unittest.TestCase):
    def test_frequency_validation(self):
        for value in (0, -1, 0.09, 100.01, math.inf, -math.inf, math.nan, "", "abc", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_frequency(value)
        self.assertEqual(validate_frequency("0.1"), 0.1)
        self.assertEqual(validate_frequency("100"), 100)

    def test_stop_interrupts_long_wait_and_allows_restart(self):
        keyboard = FakeKeyboard()
        controller = TapController(lambda: keyboard)
        try:
            controller.start(0.1)
            self.assertTrue(keyboard.tapped.wait(1))
            with self.assertRaises(RuntimeError):
                controller.start(10)
            started = time.monotonic()
            self.assertTrue(controller.stop())
            self.assertLess(time.monotonic() - started, 0.5)
            stopped_count = keyboard.calls
            time.sleep(0.04)
            self.assertEqual(keyboard.calls, stopped_count)
            keyboard.tapped.clear()
            controller.start(20)
            self.assertTrue(keyboard.tapped.wait(1))
            self.assertTrue(controller.stop())
            self.assertEqual(controller.snapshot().frequency, 20)
        finally:
            controller.stop()

    def test_failure_stops_worker(self):
        controller = TapController(lambda: FakeKeyboard(fail=True))
        try:
            controller.start(10)
            self.assertTrue(wait_for(lambda: not controller.snapshot().running))
            self.assertIn("injected failure", controller.snapshot().error)
            self.assertEqual(controller.snapshot().taps, 0)
        finally:
            controller.stop()

    def test_modifier_pauses_and_resumes(self):
        keyboard = FakeKeyboard(paused=True)
        controller = TapController(lambda: keyboard)
        try:
            controller.start(50)
            self.assertTrue(wait_for(lambda: controller.snapshot().skipped >= 2))
            self.assertTrue(controller.snapshot().paused)
            self.assertEqual(keyboard.calls, 0)
            keyboard.paused = False
            self.assertTrue(keyboard.tapped.wait(1))
            self.assertTrue(controller.stop())
        finally:
            controller.stop()

    def test_dry_run_never_constructs_keyboard(self):
        def forbidden():
            raise AssertionError("keyboard factory must not run")
        controller = TapController(forbidden)
        try:
            controller.start(100, dry_run=True)
            self.assertTrue(wait_for(lambda: controller.snapshot().taps >= 3))
            self.assertTrue(controller.stop())
            self.assertEqual(controller.snapshot().error, "")
        finally:
            controller.stop()


if __name__ == "__main__":
    unittest.main()

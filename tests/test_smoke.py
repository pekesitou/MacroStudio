"""Smoke tests that never move the real mouse or type real keys."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macro_studio import engine  # noqa: E402
from macro_studio.models import EventType, Macro, MacroEvent, Settings  # noqa: E402
from macro_studio.storage import export_rms, import_rms  # noqa: E402


class FakeMouse:
    def __init__(self):
        self.position = (0, 0)
        self.calls = []

    def press(self, button):
        self.calls.append(("press", str(button)))

    def release(self, button):
        self.calls.append(("release", str(button)))

    def scroll(self, dx, dy):
        self.calls.append(("scroll", dx, dy))


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    def press(self, key):
        self.calls.append(("press", str(key)))

    def release(self, key):
        self.calls.append(("release", str(key)))

    def type(self, text):
        self.calls.append(("type", text))


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.fake_mouse = FakeMouse()
        self.fake_keyboard = FakeKeyboard()
        self.original_mouse = engine.mouse.Controller
        self.original_keyboard = engine.keyboard.Controller
        engine.mouse.Controller = lambda: self.fake_mouse
        engine.keyboard.Controller = lambda: self.fake_keyboard

    def tearDown(self):
        engine.mouse.Controller = self.original_mouse
        engine.keyboard.Controller = self.original_keyboard

    def test_playback_logs_and_executes(self):
        logs = []
        progresses = []
        states = []
        player = engine.Player(
            lambda msg, level="info", source="SYS": logs.append((msg, level, source)),
            lambda i, total, cycle: progresses.append((i, total, cycle)),
            states.append,
        )
        macro = Macro(name="Test")
        macro.events = [
            MacroEvent(EventType.MOUSE_DOWN, 0, x=10, y=20, button="right"),
            MacroEvent(EventType.MOUSE_UP, 40, x=10, y=20, button="right"),
            MacroEvent(EventType.KEY_DOWN, 80, key="CTRL"),
            MacroEvent(EventType.KEY_UP, 90, key="CTRL"),
        ]
        self.assertTrue(player.play(macro, speed=4, repeat=1))
        deadline = time.time() + 5
        while player.playing and time.time() < deadline:
            time.sleep(0.01)
        self.assertFalse(player.playing)
        self.assertEqual(states[-1], "idle")
        self.assertTrue(any("Reproducción completada" in m for m, _, _ in logs))
        self.assertTrue(any("[001/004]" in m for m, _, _ in logs))
        self.assertEqual(self.fake_mouse.position, (10, 20))
        self.assertEqual(len([c for c in self.fake_mouse.calls if c[0] == "press"]), 1)
        self.assertEqual(len([c for c in self.fake_keyboard.calls if c[0] == "press"]), 1)
        self.assertEqual(progresses[-1][0], 4)

    def test_recorder_filters_and_times(self):
        settings = Settings(record_moves=True, record_keys=True, move_sample_ms=10)
        seen = []
        recorder = engine.Recorder(settings, lambda *a: None, seen.append)
        recorder.start()
        time.sleep(0.22)  # skip the initial "ignore my own clicks" window
        recorder.on_key("A", True)
        recorder.on_key("A", False)
        recorder.on_click(5, 6, type("B", (), {"name": "left"})(), True)
        recorder.on_move(100, 200)
        time.sleep(0.03)
        recorder.on_move(110, 210)
        events = recorder.stop()
        self.assertEqual(len(events), 5)
        self.assertEqual(events[0].type, EventType.KEY_DOWN)
        self.assertEqual(events[0].key, "A")
        self.assertEqual(events[2].type, EventType.MOUSE_DOWN)
        self.assertEqual(events[3].x, 100)
        self.assertEqual(events[4].x, 110)
        self.assertTrue(all(events[i].time_ms <= events[i + 1].time_ms for i in range(4)))
        self.assertEqual(len(seen), 5)

    def test_hotkey_detector(self):
        triggered = []
        detector = engine.HotkeyDetector(
            {"record": "f10", "play": "ctrl+f2"}, triggered.append
        )
        detector.feed("CTRL", True)
        detector.feed("F2", True)
        self.assertEqual(triggered, ["play"])
        detector.feed("F2", False)
        detector.feed("CTRL", False)
        detector.feed("F10", True)
        self.assertEqual(triggered, ["play", "record"])

    def test_rms_roundtrip(self):
        macro = Macro(name="RMS")
        macro.events = [
            MacroEvent(EventType.MOUSE_DOWN, 500, x=7, y=8, button="right"),
            MacroEvent(EventType.MOUSE_UP, 600, x=7, y=8, button="right"),
            MacroEvent(EventType.MOVE, 650, x=9, y=10),
        ]
        text = export_rms(macro)
        self.assertIn("{Delay 0.50}", text)
        self.assertIn("{RMouse down (7,8)}", text)
        self.assertIn("{Movements (0.05:9:10)}", text)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "macro.rms"
            path.write_text(text, encoding="utf-8")
            restored = import_rms(path)
        self.assertEqual(restored.event_count, 3)
        self.assertEqual(restored.events[0].button, "right")
        self.assertEqual(restored.events[2].x, 9)


class StorageTests(unittest.TestCase):
    def test_portable_marker_uses_local_data_dir(self):
        import tempfile

        from macro_studio import storage

        original_file = storage.__file__
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = root / "macro_studio"
                package.mkdir()
                storage.__file__ = str(package / "storage.py")
                (root / "portable.txt").write_text("1", encoding="ascii")

                result = storage.app_dir()
                self.assertEqual(result.resolve(), (root / "data").resolve())
                self.assertTrue(result.is_dir())
        finally:
            storage.__file__ = original_file

    def test_repeat_until_stopped_survives_settings_roundtrip(self):
        from macro_studio.models import Settings

        settings = Settings(repeat=3, repeat_until_stopped=True)
        restored = Settings.from_dict(settings.to_dict())
        self.assertTrue(restored.repeat_until_stopped)
        self.assertEqual(restored.repeat, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

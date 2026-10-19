import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from src.notifiers.google_calendar import GoogleCalendarNotifier
from src.state_manager import StateManager
from src.wifi_notifier import WiFiMonitor


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeEvents:
    def __init__(self):
        self.items = []

    def list(self, **kwargs):
        key = kwargs["privateExtendedProperty"][0].split("=", 1)[1]
        matches = [
            item
            for item in self.items
            if item["extendedProperties"]["private"]["wifi_notifier_key"] == key
        ]
        return FakeRequest({"items": matches})

    def insert(self, calendarId, body):
        event = dict(body, id=f"event-{len(self.items) + 1}")
        self.items.append(event)
        return FakeRequest(event)

    def patch(self, calendarId, eventId, body):
        event = next(item for item in self.items if item["id"] == eventId)
        event.update(body)
        return FakeRequest(event)


class FakeCalendarService:
    def __init__(self):
        self.event_list = FakeEvents()

    def events(self):
        return self.event_list


def make_calendar_notifier():
    notifier = object.__new__(GoogleCalendarNotifier)
    notifier.timezone = ZoneInfo("UTC")
    notifier.summary_prefix = "WiFi"
    notifier.max_retries = 1
    notifier.retry_delay_seconds = 0
    notifier.calendar_id = "test-calendar"
    notifier.service = FakeCalendarService()
    return notifier


class DisconnectCalendarTests(unittest.TestCase):
    def test_disconnect_schedule_end_is_updated_at_reconnect(self):
        notifier = make_calendar_notifier()
        disconnected_at = datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")).timestamp()
        reconnected_at = disconnected_at + 3600

        event_id = notifier.create_disconnect_schedule("aa:bb:cc", disconnected_at)
        event = notifier.service.event_list.items[0]
        initial_end = datetime.fromisoformat(event["end"]["dateTime"])
        self.assertEqual(
            initial_end,
            datetime.fromtimestamp(disconnected_at, ZoneInfo("UTC")) + timedelta(minutes=1),
        )

        completed = notifier.end_disconnect_schedule(
            "aa:bb:cc",
            disconnected_at,
            reconnected_at,
            event_id,
        )

        self.assertTrue(completed)
        self.assertEqual(
            datetime.fromisoformat(event["end"]["dateTime"]),
            datetime.fromtimestamp(reconnected_at, ZoneInfo("UTC")),
        )
        self.assertIn("再接続検知時刻", event["description"])

    def test_disconnect_schedule_creation_is_idempotent(self):
        notifier = make_calendar_notifier()
        disconnected_at = 1_800_000_000

        first_id = notifier.create_disconnect_schedule("aa:bb:cc", disconnected_at)
        second_id = notifier.create_disconnect_schedule("aa:bb:cc", disconnected_at)

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(notifier.service.event_list.items), 1)

    def test_disconnect_tracking_survives_state_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = str(Path(directory) / "state.json")
            state = StateManager(state_path)
            state.mark_device_disconnected("aa:bb:cc", 1000)
            state.mark_disconnect_calendar_event("aa:bb:cc", "event-1")
            state.mark_device_reconnected("aa:bb:cc", 2000)
            state.save()

            loaded_state = StateManager(state_path)
            self.assertTrue(loaded_state.load())

        self.assertEqual(loaded_state.disconnected_at["aa:bb:cc"], 1000)
        self.assertEqual(loaded_state.disconnected_calendar_event_ids["aa:bb:cc"], "event-1")
        self.assertEqual(loaded_state.disconnect_reconnected_at["aa:bb:cc"], 2000)

    def test_monitor_closes_schedule_on_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = object.__new__(WiFiMonitor)
            monitor.state_manager = StateManager(str(Path(directory) / "state.json"))
            monitor.state_manager.mark_device_disconnected("aa:bb:cc", 1000)
            monitor.state_manager.mark_disconnect_calendar_event("aa:bb:cc", "event-1")
            monitor.state_manager.mark_device_reconnected("aa:bb:cc", 2000)
            monitor.google_calendar_notifier = Mock()
            monitor.google_calendar_notifier.end_disconnect_schedule.return_value = True

            monitor._sync_disconnect_calendar_schedules({"aa:bb:cc"})

        monitor.google_calendar_notifier.end_disconnect_schedule.assert_called_once_with(
            "aa:bb:cc",
            1000,
            2000,
            "event-1",
        )
        self.assertEqual(monitor.state_manager.disconnected_at, {})


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from src.notifiers.firebase import FirebaseNotifier
from src.notifiers.google_calendar import GoogleCalendarNotifier

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_heartbeat.py"
spec = importlib.util.spec_from_file_location("check_heartbeat", SCRIPT)
check_heartbeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_heartbeat)

UTC_ZONE = ZoneInfo("UTC")


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
        return FakeRequest(
            {
                "items": [
                    item
                    for item in self.items
                    if item["extendedProperties"]["private"]["wifi_notifier_key"] == key
                ]
            }
        )

    def insert(self, calendarId, body):
        event = dict(body, id=f"event-{len(self.items) + 1}")
        self.items.append(event)
        return FakeRequest(event)

    def patch(self, calendarId, eventId, body):
        event = next(item for item in self.items if item["id"] == eventId)
        event.update(body)
        return FakeRequest(event)


class FakeService:
    def __init__(self):
        self.fake_events = FakeEvents()

    def events(self):
        return self.fake_events


def make_calendar():
    calendar = object.__new__(GoogleCalendarNotifier)
    calendar.timezone = UTC_ZONE
    calendar.summary_prefix = "🛜"
    calendar.max_retries = 1
    calendar.retry_delay_seconds = 0
    calendar.calendar_id = "test"
    calendar.service = FakeService()
    return calendar


def end_of(event):
    return datetime.fromisoformat(event["end"]["dateTime"])


class OutageScheduleTests(unittest.TestCase):
    def test_end_time_is_replaced_by_reconnect_time(self):
        calendar = make_calendar()
        started = datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()
        detected = started + 40 * 60
        reconnected = started + 90 * 60

        event_id = calendar.create_outage_schedule("raspberrypi", started, detected)
        event = calendar.service.events().items[0]
        self.assertEqual(end_of(event), datetime.fromtimestamp(detected, UTC_ZONE))

        self.assertTrue(calendar.end_outage_schedule("raspberrypi", started, reconnected, event_id))
        self.assertEqual(end_of(event), datetime.fromtimestamp(reconnected, UTC_ZONE))
        self.assertEqual(len(calendar.service.events().items), 1)
        self.assertIn("Pi接続断", event["summary"])

    def test_creation_is_idempotent(self):
        calendar = make_calendar()
        first = calendar.create_outage_schedule("raspberrypi", 1_800_000_000)
        second = calendar.create_outage_schedule("raspberrypi", 1_800_000_000)

        self.assertEqual(first, second)
        self.assertEqual(len(calendar.service.events().items), 1)

    def test_end_creates_missing_schedule(self):
        calendar = make_calendar()
        self.assertTrue(calendar.end_outage_schedule("raspberrypi", 1_800_000_000, 1_800_003_600))
        event = calendar.service.events().items[0]
        self.assertEqual(end_of(event), datetime.fromtimestamp(1_800_003_600, UTC_ZONE))

    def test_end_before_start_is_clamped(self):
        calendar = make_calendar()
        event_id = calendar.create_outage_schedule("raspberrypi", 1_800_000_000)
        calendar.end_outage_schedule("raspberrypi", 1_800_000_000, 1_799_999_000, event_id)
        event = calendar.service.events().items[0]
        self.assertGreater(end_of(event), datetime.fromtimestamp(1_800_000_000, UTC_ZONE))


class SyncCalendarTests(unittest.TestCase):
    def setUp(self):
        self.calendar = Mock()
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.started = self.now - timedelta(hours=1)

    def sync(self, stale, started, event_id=None, online_since=None):
        updates = {}
        failed = check_heartbeat._sync_calendar(
            self.calendar, "raspberrypi", stale, self.now, started, event_id, online_since, updates
        )
        return failed, updates

    def test_creates_schedule_while_outage_continues(self):
        self.calendar.create_outage_schedule.return_value = "event-1"
        failed, updates = self.sync(stale=True, started=self.started)

        self.assertFalse(failed)
        self.assertEqual(updates, {"calendar_event_id": "event-1"})
        self.calendar.create_outage_schedule.assert_called_once_with(
            "raspberrypi", self.started.timestamp(), self.now.timestamp()
        )

    def test_does_not_recreate_existing_schedule(self):
        failed, updates = self.sync(stale=True, started=self.started, event_id="event-1")

        self.assertFalse(failed)
        self.assertEqual(updates, {})
        self.calendar.create_outage_schedule.assert_not_called()

    def test_create_failure_is_retried_next_run(self):
        self.calendar.create_outage_schedule.return_value = None
        failed, updates = self.sync(stale=True, started=self.started)

        self.assertTrue(failed)
        self.assertEqual(updates, {})

    def test_reconnect_uses_online_since_and_clears_state(self):
        online_since = self.now - timedelta(minutes=10)
        self.calendar.end_outage_schedule.return_value = True
        failed, updates = self.sync(
            stale=False, started=self.started, event_id="event-1", online_since=online_since
        )

        self.assertFalse(failed)
        self.assertEqual(updates, {"outage_started_at": None, "calendar_event_id": None})
        self.calendar.end_outage_schedule.assert_called_once_with(
            "raspberrypi", self.started.timestamp(), online_since.timestamp(), "event-1"
        )

    def test_reconnect_ignores_online_since_older_than_outage(self):
        self.calendar.end_outage_schedule.return_value = True
        self.sync(
            stale=False,
            started=self.started,
            event_id="event-1",
            online_since=self.started - timedelta(days=1),
        )

        self.calendar.end_outage_schedule.assert_called_once_with(
            "raspberrypi", self.started.timestamp(), self.now.timestamp(), "event-1"
        )

    def test_reconnect_update_failure_keeps_state_for_retry(self):
        self.calendar.end_outage_schedule.return_value = False
        failed, updates = self.sync(stale=False, started=self.started, event_id="event-1")

        self.assertTrue(failed)
        self.assertEqual(updates, {})

    def test_nothing_happens_without_outage(self):
        failed, updates = self.sync(stale=False, started=None)

        self.assertFalse(failed)
        self.assertEqual(updates, {})
        self.calendar.end_outage_schedule.assert_not_called()


class HeartbeatOnlineSinceTests(unittest.TestCase):
    def make_notifier(self):
        notifier = object.__new__(FirebaseNotifier)
        notifier.project_id = "project"
        notifier.timeout_seconds = 1
        notifier._last_heartbeat_ok_at = None
        notifier._online_since = None
        notifier._get_access_token = lambda: "token"
        return notifier

    @staticmethod
    def sent_fields(mock_patch):
        return mock_patch.call_args.kwargs["json"]["fields"]

    def test_online_since_is_kept_while_heartbeat_continues(self):
        notifier = self.make_notifier()
        with patch("src.notifiers.firebase.requests.patch") as mock_patch:
            mock_patch.return_value.ok = True
            self.assertTrue(notifier.send_heartbeat("raspberrypi"))
            first = self.sent_fields(mock_patch)["online_since"]
            self.assertTrue(notifier.send_heartbeat("raspberrypi"))
            self.assertEqual(self.sent_fields(mock_patch)["online_since"], first)

    def test_online_since_is_renewed_after_a_gap(self):
        notifier = self.make_notifier()
        with patch("src.notifiers.firebase.requests.patch") as mock_patch:
            mock_patch.return_value.ok = True
            notifier.send_heartbeat("raspberrypi")
            notifier._online_since = "2000-01-01T00:00:00Z"
            notifier._last_heartbeat_ok_at -= notifier.HEARTBEAT_GAP_SECONDS + 1
            notifier.send_heartbeat("raspberrypi")
            renewed = self.sent_fields(mock_patch)["online_since"]["timestampValue"]
            self.assertNotEqual(renewed, "2000-01-01T00:00:00Z")

    def test_failed_send_does_not_start_a_new_period(self):
        notifier = self.make_notifier()
        with patch("src.notifiers.firebase.requests.patch") as mock_patch:
            mock_patch.return_value.ok = False
            mock_patch.return_value.status_code = 500
            mock_patch.return_value.text = "error"
            self.assertFalse(notifier.send_heartbeat("raspberrypi"))
        self.assertIsNone(notifier._last_heartbeat_ok_at)
        self.assertIsNone(notifier._online_since)


if __name__ == "__main__":
    unittest.main()

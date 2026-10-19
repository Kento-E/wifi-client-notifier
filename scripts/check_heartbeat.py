#!/usr/bin/env python3
"""Firestore のハートビートを確認し、途絶・復帰を FCM で通知する。

GitHub Actions の cron から実行する。通知済みフラグ（alerted）は
heartbeats/<host> ドキュメントに保存し、連続通知を防ぐ。

必要な環境変数:
  FIREBASE_CREDENTIALS_FILE  サービスアカウントJSONのパス
  FIREBASE_PROJECT_ID        Firebase プロジェクトID
  FIREBASE_REGISTRATION_TOKENS  通知先 registration token（カンマ区切り）
  HEARTBEAT_TIMEOUT_MINUTES  途絶とみなす分数（省略時 30）
  HEARTBEAT_HOSTS            監視対象ホスト名（カンマ区切り）。ドキュメントが無いホストも途絶とみなす
  GOOGLE_CALENDAR_ID         接続断を予定として登録するカレンダーID（省略時は予定登録をしない）
  GOOGLE_CALENDAR_CREDENTIALS_FILE  Calendar用サービスアカウントJSON（省略時は FIREBASE_CREDENTIALS_FILE）
  GOOGLE_CALENDAR_TIMEZONE   予定のタイムゾーン（省略時 Asia/Tokyo）

途絶を検知すると、最後に確認できた時刻を開始とする「接続断」予定を登録する。
復帰を検知すると、その予定の終了時刻を再接続時刻に更新し、1件の予定が接続断の期間になる。
"""

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.notifiers import FirebaseNotifier, GoogleCalendarNotifier  # noqa: E402

TIMEOUT = 10


def _explain_firestore_error(response: requests.Response, project_id: str) -> str:
    """Firestore のエラー応答から、次に行う操作を示すメッセージを組み立てる。"""
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    reasons = {
        d.get("reason"): d.get("metadata", {})
        for d in error.get("details", [])
        if d.get("@type", "").endswith("ErrorInfo")
    }

    if "SERVICE_DISABLED" in reasons:
        url = reasons["SERVICE_DISABLED"].get(
            "activationUrl",
            "https://console.developers.google.com/apis/api/"
            f"firestore.googleapis.com/overview?project={project_id}",
        )
        return (
            "Cloud Firestore API が有効化されていません。次のURLで「有効にする」を押し、"
            f"数分待ってから再実行してください: {url}"
        )
    if response.status_code == 404:
        return (
            "Firestore の (default) データベースが未作成です。次のURLで作成してください"
            "（ネイティブモード）: "
            f"https://console.firebase.google.com/project/{project_id}/firestore"
        )
    if response.status_code == 403:
        return (
            "サービスアカウントに Firestore の権限がありません。次のURLで該当アカウントに"
            "ロール「Cloud Datastore User」を付与してください: "
            f"https://console.cloud.google.com/iam-admin/iam?project={project_id}"
        )
    return f"Firestore の取得に失敗しました: status={response.status_code} body={response.text}"


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _timestamp_field(fields: dict, name: str) -> datetime | None:
    raw = fields.get(name, {}).get("timestampValue")
    return _parse_time(raw) if raw else None


def _encode_field(value: object) -> dict:
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, datetime):
        return {"timestampValue": value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return {"stringValue": str(value)}


def _build_calendar() -> GoogleCalendarNotifier | None:
    """接続断の予定登録に使うカレンダー通知を作る。未設定なら None を返す。"""
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
    if not calendar_id:
        logging.info("GOOGLE_CALENDAR_ID が未設定のため接続断の予定登録は行いません")
        return None
    credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE") or os.environ.get(
        "FIREBASE_CREDENTIALS_FILE", ""
    )
    try:
        return GoogleCalendarNotifier(
            credentials_file=credentials_file,
            calendar_id=calendar_id,
            timezone_name=os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Tokyo"),
        )
    except Exception as e:
        logging.error("Googleカレンダーの初期化に失敗したため予定登録をスキップします: %s", e)
        return None


def _sync_calendar(
    calendar: GoogleCalendarNotifier,
    host: str,
    stale: bool,
    now: datetime,
    outage_started: datetime | None,
    event_id: str | None,
    online_since: datetime | None,
    updates: dict,
) -> bool:
    """接続断の予定を、途絶中は作成し、復帰後は終了時刻を再接続時刻へ更新する。

    Returns:
        処理に失敗した場合は True（次回の実行で再試行する）
    """
    if outage_started is None:
        return False

    if stale:
        if event_id is not None:
            return False
        new_id = calendar.create_outage_schedule(host, outage_started.timestamp(), now.timestamp())
        if new_id is None:
            return True
        updates["calendar_event_id"] = new_id
        return False

    reconnected_at = online_since if online_since and online_since > outage_started else now
    if not calendar.end_outage_schedule(
        host, outage_started.timestamp(), reconnected_at.timestamp(), event_id
    ):
        return True
    updates["outage_started_at"] = None
    updates["calendar_event_id"] = None
    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    project_id = os.environ["FIREBASE_PROJECT_ID"]
    tokens = [t for t in os.environ["FIREBASE_REGISTRATION_TOKENS"].split(",") if t.strip()]
    timeout_minutes = int(os.getenv("HEARTBEAT_TIMEOUT_MINUTES", "30"))
    expected_hosts = {h.strip() for h in os.getenv("HEARTBEAT_HOSTS", "").split(",") if h.strip()}

    notifier = FirebaseNotifier(
        project_id=project_id,
        credentials_file=os.environ["FIREBASE_CREDENTIALS_FILE"],
        registration_tokens=tokens,
        timeout_seconds=TIMEOUT,
    )
    headers = {"Authorization": f"Bearer {notifier._get_access_token()}"}
    base = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        "/databases/(default)/documents/heartbeats"
    )

    response = requests.get(base, headers=headers, timeout=TIMEOUT)
    if not response.ok:
        logging.error("%s", _explain_firestore_error(response, project_id))
        return 1
    fields_by_host = {
        doc["name"].rsplit("/", 1)[-1]: doc.get("fields", {})
        for doc in response.json().get("documents", [])
    }
    hosts = expected_hosts | set(fields_by_host)
    if not hosts:
        # 監視対象が1つも無い状態は監視が機能していないので、成功扱いにしない
        logging.error(
            "監視対象がありません。Variables の HEARTBEAT_HOSTS を設定し、"
            "Pi がハートビートを送信しているか確認してください"
        )
        return 1

    calendar = _build_calendar()
    now = datetime.now(UTC)
    failed = False
    for host in sorted(hosts):
        fields = fields_by_host.get(host, {})
        last_seen_raw = fields.get("last_seen", {}).get("timestampValue")
        alerted = fields.get("alerted", {}).get("booleanValue", False)
        outage_started = _timestamp_field(fields, "outage_started_at")
        event_id = fields.get("calendar_event_id", {}).get("stringValue")
        # 一度もハートビートが届いていないホストも途絶とみなす
        stale = last_seen_raw is None or now - _parse_time(last_seen_raw) > timedelta(
            minutes=timeout_minutes
        )
        logging.info("%s: last_seen=%s stale=%s alerted=%s", host, last_seen_raw, stale, alerted)

        # None を入れたフィールドは Firestore から削除する
        updates: dict[str, object] = {}
        if stale and outage_started is None:
            # 切断前に最後に確認できた時刻を、接続断の開始時刻にする
            outage_started = _parse_time(last_seen_raw) if last_seen_raw else now
            updates["outage_started_at"] = outage_started

        if stale and not alerted:
            if last_seen_raw is None:
                body = "ハートビートを一度も受信していません（Pi のコードが古い可能性があります）"
            else:
                minutes = int((now - _parse_time(last_seen_raw)).total_seconds() // 60)
                body = f"最終確認: {last_seen_raw}（{minutes}分前）"
            if notifier.send_message(
                f"🚨: {host} のハートビートが途絶しました",
                body,
                {"notification_type": "heartbeat_lost", "host": host},
            ):
                updates["alerted"] = True
            else:
                failed = True  # 通知失敗時はフラグを更新せず次回再試行する
        elif not stale and alerted:
            if notifier.send_message(
                f"✅: {host} が復帰しました",
                f"最終確認: {last_seen_raw}",
                {"notification_type": "heartbeat_recovered", "host": host},
            ):
                updates["alerted"] = False
            else:
                failed = True

        if calendar is not None and _sync_calendar(
            calendar,
            host,
            stale,
            now,
            outage_started,
            event_id,
            _timestamp_field(fields, "online_since"),
            updates,
        ):
            failed = True

        if not updates:
            continue
        patch = requests.patch(
            f"{base}/{host}",
            params={"updateMask.fieldPaths": list(updates)},
            headers=headers,
            json={
                "fields": {
                    name: _encode_field(value)
                    for name, value in updates.items()
                    if value is not None
                }
            },
            timeout=TIMEOUT,
        )
        patch.raise_for_status()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

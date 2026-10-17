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
"""

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.notifiers import FirebaseNotifier  # noqa: E402

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

    now = datetime.now(UTC)
    failed = False
    for host in sorted(hosts):
        fields = fields_by_host.get(host, {})
        last_seen_raw = fields.get("last_seen", {}).get("timestampValue")
        alerted = fields.get("alerted", {}).get("booleanValue", False)
        # 一度もハートビートが届いていないホストも途絶とみなす
        stale = last_seen_raw is None or now - _parse_time(last_seen_raw) > timedelta(
            minutes=timeout_minutes
        )
        logging.info("%s: last_seen=%s stale=%s alerted=%s", host, last_seen_raw, stale, alerted)

        if stale and not alerted:
            if last_seen_raw is None:
                body = "ハートビートを一度も受信していません（Pi のコードが古い可能性があります）"
            else:
                minutes = int((now - _parse_time(last_seen_raw)).total_seconds() // 60)
                body = f"最終確認: {last_seen_raw}（{minutes}分前）"
            ok = notifier.send_message(
                f"🚨: {host} のハートビートが途絶しました",
                body,
                {"notification_type": "heartbeat_lost", "host": host},
            )
            new_alerted = True
        elif not stale and alerted:
            ok = notifier.send_message(
                f"✅: {host} が復帰しました",
                f"最終確認: {last_seen_raw}",
                {"notification_type": "heartbeat_recovered", "host": host},
            )
            new_alerted = False
        else:
            continue

        if not ok:
            failed = True  # 通知失敗時はフラグを更新せず次回再試行する
            continue
        patch = requests.patch(
            f"{base}/{host}",
            params={"updateMask.fieldPaths": "alerted"},
            headers=headers,
            json={"fields": {"alerted": {"booleanValue": new_alerted}}},
            timeout=TIMEOUT,
        )
        patch.raise_for_status()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

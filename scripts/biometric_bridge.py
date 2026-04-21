#!/usr/bin/env python
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib import error, request

try:
    from zk import ZK
except Exception as exc:
    print(f"pyzk import failed: {exc}", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read biometric logs from a local device and push them to the remote Django endpoint."
    )
    parser.add_argument("--server-url", required=True, help="Remote endpoint URL, e.g. https://example.com/employ/biometric/push/")
    parser.add_argument("--token", required=True, help="Value of BIOMETRIC_PUSH_TOKEN on the remote Django server")
    parser.add_argument("--device-ip", required=True, help="Local biometric device IP address")
    parser.add_argument("--device-port", type=int, default=4370, help="Local biometric device port")
    parser.add_argument("--device-serial", required=True, help="Serial number of the BiometricDevice saved on the remote server")
    parser.add_argument("--timeout", type=int, default=5, help="Timeout when connecting to the biometric device")
    parser.add_argument("--state-file", default="biometric_bridge_state.json", help="Path to a local state file used to avoid re-pushing old logs")
    parser.add_argument("--overlap-minutes", type=int, default=2, help="Overlap window to keep around the last synced timestamp")
    return parser.parse_args()


def load_state(path):
    state_path = Path(path)
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path, state):
    state_path = Path(path)
    state_path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def resolve_punch_type(record):
    punch_code = getattr(record, "punch", None)
    if punch_code == 0:
        return "check_in"
    if punch_code == 1:
        return "check_out"
    if punch_code == 2:
        return "break_out"
    if punch_code == 3:
        return "break_in"
    return "unknown"


def fetch_records(args):
    zk = ZK(
        args.device_ip,
        port=args.device_port,
        timeout=args.timeout,
        ommit_ping=True,
    )
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()
        return conn.get_attendance() or []
    finally:
        if conn:
            try:
                conn.enable_device()
            except Exception:
                pass
            try:
                conn.disconnect()
            except Exception:
                pass


def filter_and_serialize(records, last_synced_at, overlap_minutes):
    since = None
    if last_synced_at:
        since = datetime.fromisoformat(last_synced_at) - timedelta(minutes=overlap_minutes)

    payload = []
    latest_timestamp = None
    for record in records:
        timestamp = getattr(record, "timestamp", None)
        if not timestamp:
            continue
        if since and timestamp < since:
            continue

        device_user_id = str(getattr(record, "user_id", "") or "").strip()
        if not device_user_id:
            continue

        payload.append({
            "device_user_id": device_user_id,
            "punch_time": timestamp.isoformat(),
            "punch_type": resolve_punch_type(record),
            "raw_data": {
                "uid": getattr(record, "uid", None),
                "status": getattr(record, "status", None),
                "punch": getattr(record, "punch", None),
            },
        })
        if latest_timestamp is None or timestamp > latest_timestamp:
            latest_timestamp = timestamp

    return payload, latest_timestamp


def push_logs(args, logs):
    body = json.dumps({
        "device_serial": args.device_serial,
        "logs": logs,
    }).encode("utf-8")
    req = request.Request(
        args.server_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=max(args.timeout, 10)) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw)


def main():
    args = parse_args()
    state = load_state(args.state_file)
    state_key = f"{args.server_url}|{args.device_serial}"
    last_synced_at = state.get(state_key)

    records = fetch_records(args)
    logs, latest_timestamp = filter_and_serialize(records, last_synced_at, args.overlap_minutes)
    if not logs:
        print("No new logs to push.")
        return 0

    try:
        status, response_payload = push_logs(args, logs)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Push failed with HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Push failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"http_status": status, **response_payload}, ensure_ascii=False))

    if latest_timestamp is not None and response_payload.get("ok"):
        state[state_key] = latest_timestamp.isoformat()
        save_state(args.state_file, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

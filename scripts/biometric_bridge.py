#!/usr/bin/env python
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib import error, request

try:
    from zk import ZK
except Exception as exc:
    print(f"pyzk import failed: {exc}", file=sys.stderr)
    sys.exit(1)


DEFAULT_CONFIG = "biometric_bridge_config.json"
DEFAULT_STATE = "biometric_bridge_state.json"
DEFAULT_LOG = "biometric_bridge.log"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read biometric logs from a local device and push them to the remote Django endpoint."
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to a JSON config file")
    parser.add_argument("--server-url", help="Remote endpoint URL, e.g. https://example.com/employ/biometric/push/")
    parser.add_argument("--token", help="Value of BIOMETRIC_PUSH_TOKEN on the remote Django server")
    parser.add_argument("--device-ip", help="Local biometric device IP address")
    parser.add_argument("--device-port", type=int, help="Local biometric device port")
    parser.add_argument("--device-serial", help="Serial number of the BiometricDevice saved on the remote server")
    parser.add_argument("--timeout", type=int, help="Timeout when connecting to the biometric device")
    parser.add_argument("--state-file", help="Path to a local state file used to avoid re-pushing old logs")
    parser.add_argument("--overlap-minutes", type=int, help="Overlap window to keep around the last synced timestamp")
    parser.add_argument("--interval-seconds", type=int, help="Polling interval when running continuously")
    parser.add_argument("--log-file", help="Path to the log file")
    parser.add_argument("--once", action="store_true", help="Run a single sync cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Keep syncing in the background")
    return parser.parse_args()


def load_json_file(path):
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_state(path):
    return load_json_file(path)


def save_state(path, state):
    Path(path).write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def setup_logging(log_file):
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def build_runtime_config(args):
    config = {
        "server_url": None,
        "token": None,
        "device_ip": None,
        "device_port": 4370,
        "device_serial": None,
        "timeout": 5,
        "state_file": DEFAULT_STATE,
        "overlap_minutes": 2,
        "interval_seconds": 60,
        "log_file": DEFAULT_LOG,
        "run_mode": "once",
    }

    file_config = load_json_file(args.config)
    if isinstance(file_config, dict):
        config.update({key: value for key, value in file_config.items() if value not in (None, "")})

    for key in (
        "server_url",
        "token",
        "device_ip",
        "device_port",
        "device_serial",
        "timeout",
        "state_file",
        "overlap_minutes",
        "interval_seconds",
        "log_file",
    ):
        arg_name = key.replace("-", "_")
        value = getattr(args, arg_name, None)
        if value not in (None, ""):
            config[key] = value

    if args.loop:
        config["run_mode"] = "loop"
    elif args.once:
        config["run_mode"] = "once"

    missing = [key for key in ("server_url", "token", "device_ip", "device_serial") if not config.get(key)]
    if missing:
        raise SystemExit(f"Missing required settings: {', '.join(missing)}")
    return config


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


def fetch_records(config):
    zk = ZK(
        config["device_ip"],
        port=int(config["device_port"]),
        timeout=int(config["timeout"]),
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
                logging.debug("Failed to re-enable device", exc_info=True)
            try:
                conn.disconnect()
            except Exception:
                logging.debug("Failed to disconnect device", exc_info=True)


def filter_and_serialize(records, last_synced_at, overlap_minutes):
    since = None
    if last_synced_at:
        since = datetime.fromisoformat(last_synced_at) - timedelta(minutes=int(overlap_minutes))

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


def push_logs(config, logs):
    body = json.dumps({
        "device_serial": config["device_serial"],
        "logs": logs,
    }).encode("utf-8")
    req = request.Request(
        config["server_url"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['token']}",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "User-Agent": DEFAULT_USER_AGENT,
            "X-Biometric-Bridge": "1",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=max(int(config["timeout"]), 10)) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw)


def run_cycle(config):
    state = load_state(config["state_file"])
    state_key = f"{config['server_url']}|{config['device_serial']}"
    last_synced_at = state.get(state_key)

    records = fetch_records(config)
    logs, latest_timestamp = filter_and_serialize(records, last_synced_at, config["overlap_minutes"])
    if not logs:
        logging.info("No new logs to push.")
        return 0

    try:
        status, response_payload = push_logs(config, logs)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logging.error("Push failed with HTTP %s: %s", exc.code, body)
        return 1
    except Exception as exc:
        logging.error("Push failed: %s", exc)
        return 1

    logging.info(json.dumps({"http_status": status, **response_payload}, ensure_ascii=False))

    if latest_timestamp is not None and response_payload.get("ok"):
        state[state_key] = latest_timestamp.isoformat()
        save_state(config["state_file"], state)
    return 0


def run_loop(config):
    interval_seconds = max(int(config["interval_seconds"]), 5)
    logging.info("Biometric bridge started in loop mode. Interval=%s seconds", interval_seconds)
    while True:
        try:
            run_cycle(config)
        except Exception:
            logging.exception("Unexpected bridge cycle error")
        time.sleep(interval_seconds)


def main():
    args = parse_args()
    config = build_runtime_config(args)
    setup_logging(config["log_file"])

    if config["run_mode"] == "loop":
        run_loop(config)
        return 0
    return run_cycle(config)


if __name__ == "__main__":
    raise SystemExit(main())

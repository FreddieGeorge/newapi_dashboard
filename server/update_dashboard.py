#!/usr/bin/env python3
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


CONFIG_DIR = Path(
    os.environ.get("NEW_API_CONFIG_DIR", "~/.config/newapi-dashboard")
).expanduser()
EXPORT_URL_FILE = Path(
    os.environ.get("NEW_API_EXPORT_URL_FILE", str(CONFIG_DIR / "export_url"))
).expanduser()
USER_ID_FILE = Path(
    os.environ.get("NEW_API_USER_ID_FILE", str(CONFIG_DIR / "user_id"))
).expanduser()
TOKEN_FILE = Path(
    os.environ.get("NEW_API_TOKEN_FILE", str(CONFIG_DIR / "access_token"))
).expanduser()
DATA_DIR = Path(
    os.environ.get("NEW_API_DATA_DIR", "/var/www/newapi-dashboard/data")
).expanduser()
MONTHS_DIR = DATA_DIR / "months"
STATE_DIR = Path(
    os.environ.get("NEW_API_STATE_DIR", "~/newapi-dashboard-runtime/state")
).expanduser()
TIME_ZONE = timezone(timedelta(hours=8))
REQUIRED_FIELDS = {"时间", "类型", "令牌名称", "模型名称", "花费", "请求ID"}


def read_setting(environment_name, file_path):
    value = os.environ.get(environment_name, "").strip()
    if value:
        return value
    try:
        value = file_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise RuntimeError(
            f"Missing {environment_name}; set it or create {file_path}"
        )
    if not value:
        raise RuntimeError(f"Configuration file is empty: {file_path}")
    return value


def add_months(value, offset):
    month_index = value.year * 12 + value.month - 1 + offset
    return datetime(month_index // 12, month_index % 12 + 1, 1, tzinfo=TIME_ZONE)


def download_month(month_start, export_url, user_id, token):
    month_end = add_months(month_start, 1)
    query = urllib.parse.urlencode({
        "type": 0,
        "start_timestamp": int(month_start.timestamp()),
        "end_timestamp": int(month_end.timestamp()) - 1,
    })
    request = urllib.request.Request(
        f"{export_url}?{query}",
        headers={
            "New-Api-User": user_id,
            "Authorization": f"Bearer {token}",
            "User-Agent": "newapi-dashboard/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read()

    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or [])
    missing = REQUIRED_FIELDS - fields
    if missing:
        raise RuntimeError(f"Invalid CSV, missing fields: {', '.join(sorted(missing))}")

    rows = list(reader)
    return payload, len(rows)


def publish_month(month_start, payload):
    month_id = month_start.strftime("%Y-%m")
    year_dir = MONTHS_DIR / month_start.strftime("%Y")
    year_dir.mkdir(parents=True, exist_ok=True)
    target = year_dir / f"{month_id}.csv"
    temporary = target.with_suffix(".csv.tmp")
    temporary.write_bytes(payload)
    os.chmod(temporary, 0o644)
    os.replace(temporary, target)
    return target


def update_month(month_start, export_url, user_id, token):
    payload, row_count = download_month(month_start, export_url, user_id, token)
    target = publish_month(month_start, payload)
    print(f"Published {month_start:%Y-%m}: {row_count} rows -> {target}")


def mark_finalized(month_start):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    marker = STATE_DIR / f"{month_start:%Y-%m}.finalized"
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(datetime.now(TIME_ZONE).isoformat(), encoding="utf-8")
    os.replace(temporary, marker)
    return marker


def rebuild_manifest(current_month):
    months = []
    for path in sorted(MONTHS_DIR.glob("*/????-??.csv")):
        month_id = path.stem
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
        months.append({
            "id": month_id,
            "year": int(month_id[:4]),
            "month": int(month_id[5:7]),
            "file": f"months/{month_id[:4]}/{month_id}.csv",
            "rows": row_count,
            "complete": month_id < current_month.strftime("%Y-%m"),
        })

    manifest = {
        "version": 1,
        "updatedAt": datetime.now(TIME_ZONE).isoformat(),
        "months": months,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = DATA_DIR / "index.json.tmp"
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.chmod(temporary, 0o644)
    os.replace(temporary, DATA_DIR / "index.json")


def main():
    supported_arguments = {"--refresh-previous"}
    unknown_arguments = set(sys.argv[1:]) - supported_arguments
    if unknown_arguments:
        raise RuntimeError(f"Unknown arguments: {', '.join(sorted(unknown_arguments))}")

    export_url = read_setting("NEW_API_EXPORT_URL", EXPORT_URL_FILE)
    user_id = read_setting("NEW_API_USER_ID", USER_ID_FILE)
    token = read_setting("NEW_API_ACCESS_TOKEN", TOKEN_FILE)

    now = datetime.now(TIME_ZONE)
    current_month = datetime(now.year, now.month, 1, tzinfo=TIME_ZONE)
    previous_month = add_months(current_month, -1)

    update_month(current_month, export_url, user_id, token)

    previous_marker = STATE_DIR / f"{previous_month:%Y-%m}.finalized"
    if "--refresh-previous" in sys.argv[1:] or not previous_marker.exists():
        update_month(previous_month, export_url, user_id, token)
        marker = mark_finalized(previous_month)
        print(f"Finalized {previous_month:%Y-%m}: {marker}")
    else:
        print(f"Skipped finalized month: {previous_month:%Y-%m}")

    rebuild_manifest(current_month)
    print(f"Dashboard updated at {datetime.now(TIME_ZONE).isoformat()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Update failed: {error}", file=sys.stderr)
        raise

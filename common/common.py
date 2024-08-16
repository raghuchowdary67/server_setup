import fcntl
import json
import logging
import os
from datetime import datetime

# Global variable to store the start time of the service
system_start_time = datetime.now()

# Get the logger for this module
logger = logging.getLogger(__name__)


def calculate_uptime(service_start_time: datetime) -> tuple:
    """
    Calculate the uptime of the service since its start time.

    Args:
        service_start_time (datetime): The datetime when the service was started.

    Returns:
        tuple: A tuple containing the uptime in days, hours, and minutes.
    """
    uptime_delta = datetime.now() - service_start_time
    uptime_days = uptime_delta.days
    uptime_hours, remainder = divmod(uptime_delta.seconds, 3600)
    uptime_minutes, _ = divmod(remainder, 60)
    return uptime_days, uptime_hours, uptime_minutes


def parse_status_file(file_path):
    if not os.path.exists(file_path):
        return f"No file {file_path} exists"

    with open(file_path, 'r') as file:
        fcntl.flock(file, fcntl.LOCK_SH)
        content = file.read()
        fcntl.flock(file, fcntl.LOCK_UN)

    try:
        logger.info(f"File read parsing the json: {content}")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.info(f"Error while parsing the file: {e}")
        return f"Error parsing JSON in {file_path}: {e}"

    logger.info(f"File parsed and data is: {data.get('cpu_percent', 0.0)}")
    return {
        "cpu_percent": data.get('cpu_percent', 0.0),
        "memory_percent": data.get('memory_percent', 0.0),
        "bandwidth": {
            "main_upload_speed": data.get('main_upload_speed', '0 B/s'),
            "main_download_speed": data.get('main_download_speed', '0 B/s'),
            "instance_total_upload": data.get('instance_total_upload', '0 KB'),
            "instance_total_download": data.get('instance_total_download', '0 KB'),
            "total_bandwidth_used": data.get('total_bandwidth_used', '0 GB')
        }
    }

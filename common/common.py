import fcntl
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
        return "No data exists"

    with open(file_path, 'r') as file:
        fcntl.flock(file, fcntl.LOCK_SH)
        content = file.read()
        fcntl.flock(file, fcntl.LOCK_UN)

    data = {}
    try:
        data['cpu_percent'] = float(next(line.split(': ')[1].strip().replace('%', '') for line in content.split('\n') if
                                         line.startswith("CPU Usage")))
        data['memory_percent'] = float(next(
            line.split(': ')[1].strip().replace('%', '') for line in content.split('\n') if
            line.startswith("Memory Usage")))
        data['main_upload_speed'] = next(line.split(': ')[1].split(',')[0].strip() for line in content.split('\n') if
                                         line.startswith("Current Upload Speed"))
        data['main_download_speed'] = next(line.split(': ')[2].split(',')[0].strip() for line in content.split('\n') if
                                           line.startswith("Current Upload Speed"))
        data['instance_total_upload'] = next(
            line.split(': ')[1].split(',')[0].strip() for line in content.split('\n') if
            line.startswith("Instance Total Upload"))
        data['instance_total_download'] = next(
            line.split(': ')[2].split(',')[0].strip() for line in content.split('\n') if
            line.startswith("Instance Total Upload"))
        data['total_bandwidth_used'] = next(line.split(': ')[1].strip() for line in content.split('\n') if
                                            line.startswith("AWS Monthly Total Bandwidth Used"))

    except StopIteration:
        logger.info("No data Exists in the file")
        return "No data exists"

    logger.info("Data found: "+str(data.get('cpu_percent', 0.0)))
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

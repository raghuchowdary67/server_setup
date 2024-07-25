#!/usr/bin/env python3

import psutil
import time
import os
import math
import boto3
from datetime import datetime, timedelta
import subprocess

home = os.environ.get("HOME", "/home/ec2-user")


def convert_size(size_bytes):
    """
    Convert bytes to a human-readable format (KB, MB, GB, TB).

    Args:
    size_bytes (int): The size in bytes.

    Returns:
    str: The human-readable size.
    """
    if size_bytes < 0:
        return "Invalid size"
    if size_bytes == 0:
        return "0B"

    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_name[i]}"


def get_network_stats():
    """Get network stats"""
    net_io = psutil.net_io_counters()
    return net_io.bytes_sent, net_io.bytes_recv


def get_system_stats():
    """Get system stats"""
    ec2_cpu_usage = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    ec2_mem_usage = mem.percent
    return ec2_cpu_usage, ec2_mem_usage


def get_billing_period():
    """Get the current AWS billing period"""
    now = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    end = start + timedelta(days=32)
    end = datetime(end.year, end.month, 1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def get_aws_bandwidth_usage(ec2_instance_id):
    cloudwatch = boto3.client('cloudwatch', 'us-east-1')

    def get_metric_sum(metric_name):
        start, end = get_billing_period()
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName=metric_name,
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': ec2_instance_id
                },
            ],
            StartTime=start,
            EndTime=end,
            Period=86400,
            Statistics=['Sum'],
            Unit='Bytes'
        )
        data_points = response['Datapoints']
        return sum(dp['Sum'] for dp in data_points)

    network_in = get_metric_sum('NetworkIn')
    network_out = get_metric_sum('NetworkOut')
    total_bandwidth = network_in + network_out
    return total_bandwidth

def get_instance_id():
    try:
        result = subprocess.run(['ec2-metadata', '--instance-id'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        if result.returncode == 0:
            return result.stdout.strip().split(": ")[1]
        else:
            print(f"Error fetching instance ID: {result.stderr}")
            return None
    except Exception as e:
        print(f"Unable to fetch instance ID: {e}")
        return None

# Ensure the reports directory exists
reports_dir = os.path.join(home, "reports")
os.makedirs(reports_dir, exist_ok=True)

# File to store stats
file_path = os.path.join(reports_dir, "system_network_usage.txt")

# Previous values for calculating speed
prev_sent, prev_recv = get_network_stats()

# Initial total data usage
initial_sent = prev_sent
initial_recv = prev_recv

# Cache AWS bandwidth usage and update every hour
aws_cache_duration = 600
last_aws_update = time.time() - aws_cache_duration  # Force immediate update on first run
total_bandwidth_used = 0
instance_id = get_instance_id()
if instance_id:
    while True:
        current_time = time.time()

        # Update AWS bandwidth usage if cache duration has passed
        if current_time - last_aws_update >= aws_cache_duration:
            total_bandwidth_used = get_aws_bandwidth_usage(instance_id)
            print(convert_size(total_bandwidth_used))
            last_aws_update = current_time

        current_sent, current_recv = get_network_stats()
        cpu_usage, mem_usage = get_system_stats()

        sent_speed = (current_sent - prev_sent) / 1024  # KB/s
        recv_speed = (current_recv - prev_recv) / 1024  # KB/s

        total_sent = current_sent - initial_sent
        total_recv = current_recv - initial_recv

        prev_sent, prev_recv = current_sent, current_recv
        with open(file_path, 'w') as file:
            file.write(f"CPU Usage: {cpu_usage:.2f}%\n")
            file.write(f"Memory Usage: {mem_usage:.2f}%\n")
            file.write(f"Current Upload Speed: {convert_size(sent_speed * 1024)}/s, Current Download Speed: {convert_size(recv_speed * 1024)}/s\n")
            file.write(f"Current Instance session Total upload and Downloaded Data\n")
            file.write(f"Instance Total Upload: {convert_size(total_sent)}, Instance Total Download: {convert_size(total_recv)}\n")
            file.write(f"AWS Monthly Total Bandwidth Used: {convert_size(total_bandwidth_used)}\n")

        # Sleep for 1 second to update CPU and memory usage frequently
        time.sleep(1)
else:
    print("No instance id was found....")
    with open(file_path, 'w') as file:
        file.write("No instance id was found....")
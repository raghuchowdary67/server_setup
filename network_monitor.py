#!/usr/bin/env python3

import psutil
import time
import fcntl
import os
import math
from datetime import datetime, timedelta, UTC
import subprocess
import platform
import sys
import json

home = os.environ.get("HOME")
print("Home directory is: " + home)


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
    """Get network stats."""
    net_io = psutil.net_io_counters()
    return net_io.bytes_sent, net_io.bytes_recv


def get_system_stats():
    """Get system stats."""
    server_cpu_usage = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    server_mem_usage = mem.percent
    return server_cpu_usage, server_mem_usage


# Determine if this is running on EC2
is_ec2 = len(sys.argv) > 1 and sys.argv[1].lower().startswith('ec2_')


def get_billing_period():
    """Get the current AWS billing period."""
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, 1)
    end = start + timedelta(days=32)
    end = datetime(end.year, end.month, 1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def get_aws_bandwidth_usage(ec2_instance_id):
    # IMPORTANT: To Access cloud watch setup the IAM role using below steps
    # Create an IAM Role:
    # Go to AWS Management Console:
    # Navigate to the IAM (Identity and Access Management) service.
    # Select "Roles" from the sidebar.
    # Click "Create role."
    # Select EC2 Service:
    # Choose the "AWS service" type and select "EC2" as the service that will use this role.
    # Attach Policies:
    # Attach the necessary policies to your role (e.g., CloudWatchReadOnlyAccess, AmazonS3ReadOnlyAccess, etc.).
    # Name and Create Role:
    # Provide a name for your role (e.g., MyEC2Role) and create it.
    # Attach the IAM Role to Your EC2 Instance:
    # Go to EC2 Dashboard:
    # Navigate to the EC2 Dashboard in the AWS Management Console.
    # Select Your Instance:
    # Choose the EC2 instance where you want to attach the IAM role.
    # Actions > Security > Modify IAM Role:
    # Click on "Actions" > "Security" > "Modify IAM Role."
    # Attach Role:
    # Select the IAM role you created and attach it to your instance.

    """Get AWS EC2 instance bandwidth usage."""
    import boto3  # Only import boto3 if running on EC2

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
        # Determine the OS type
        os_type = platform.system()

        # Use the appropriate command based on the OS
        if os_type == "Linux":
            # Check if it's Amazon Linux (AMI)
            with open('/etc/os-release') as f:
                os_release = f.read()
            if 'Amazon Linux' in os_release:
                command = 'ec2-metadata'
            else:  # Assume Ubuntu for other Linux distributions
                command = 'ec2metadata'

            # Run the command
            result = subprocess.run([command, '--instance-id'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)

            if result.returncode == 0:
                return result.stdout.strip().split(": ")[1] if command == 'ec2-metadata' else result.stdout.strip()
            else:
                print(f"Error fetching instance ID: {result.stderr}")
                return None
        else:
            print(f"Unsupported OS: {os_type}")
            return None

    except Exception as e:
        print(f"Unable to fetch instance ID: {e}")
        return None


def write_json(usage_file_path, data):
    with open(usage_file_path, 'w') as usage_file:
        fcntl.flock(usage_file, fcntl.LOCK_EX)
        json.dump(data, usage_file, indent=4)
        fcntl.flock(usage_file, fcntl.LOCK_UN)


def generate_metrics(is_ec2_instance, usage_file_path, ec2_instance_id=None):
    aws_cache_duration = 600
    last_aws_update = time.time() - aws_cache_duration  # Force immediate update on first run
    total_bandwidth_used = 0

    current_prev_sent, current_prev_recv = get_network_stats()
    current_initial_sent = current_prev_sent
    current_initial_recv = current_prev_recv

    while True:
        current_time = time.time()
        if is_ec2_instance and ec2_instance_id and current_time - last_aws_update >= aws_cache_duration:
            total_bandwidth_used = get_aws_bandwidth_usage(ec2_instance_id)
            last_aws_update = current_time

        current_sent, current_recv = get_network_stats()
        cpu_usage, mem_usage = get_system_stats()

        sent_speed = (current_sent - current_prev_sent) / 1024  # KB/s
        recv_speed = (current_recv - current_prev_recv) / 1024  # KB/s

        total_sent = current_sent - current_initial_sent
        total_recv = current_recv - current_initial_recv

        current_prev_sent, current_prev_recv = current_sent, current_recv

        data = {
            "cpu_percent": cpu_usage,
            "memory_percent": mem_usage,
            "current_upload_speed": f"{convert_size(sent_speed * 1024)}/s",
            "current_download_speed": f"{convert_size(recv_speed * 1024)}/s",
            "instance_total_upload": convert_size(total_sent),
            "instance_total_download": convert_size(total_recv)
        }
        print(str(total_sent))
        print(str(total_recv))
        data["aws_monthly_total_bandwidth_used"] = convert_size(total_sent + total_recv)

        # if is_ec2_instance:
        #     data["aws_monthly_total_bandwidth_used"] = convert_size(total_bandwidth_used)
        # else:
        #     print(str(total_sent))
        #     print(str(total_recv))
        #     data["aws_monthly_total_bandwidth_used"] = convert_size(total_sent + total_recv)

        write_json(usage_file_path, data)
        time.sleep(2)


# Ensure the reports directory exists
reports_dir = os.path.join(home, "reports")
os.makedirs(reports_dir, exist_ok=True)

# File to store stats
file_path = os.path.join(reports_dir, "system_network_usage.json")

# Previous values for calculating speed
prev_sent, prev_recv = get_network_stats()

# Initial total data usage
initial_sent = prev_sent
initial_recv = prev_recv
instance_id = None

if is_ec2:
    instance_id = get_instance_id()

    if instance_id:
        generate_metrics(is_ec2, file_path, instance_id)
    else:
        print("No instance ID was found....")
        with open(file_path, 'w') as file:
            json.dump({"error": "No instance ID was found...."}, file, indent=4)

else:
    generate_metrics(is_ec2, file_path)

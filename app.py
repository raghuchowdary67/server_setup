import logging
import os
import subprocess
import threading
import time
from collections import deque, defaultdict

import docker
import psutil
import requests  # to make external HTTP requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_restx import Api, Resource, fields

from common.common import calculate_uptime, system_start_time, parse_status_file

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

app = Flask(__name__)
api = Api(app, version='2.2', title='System Monitoring API',
          description='A simple API to monitor system and Docker container stats')

# Enable CORS for all routes and origins
CORS(app)

client = docker.from_env()
home = "/home/redbull"
system_type = os.getenv('SYSTEM_TYPE', 'Main Server')
instance_type = os.getenv('INSTANCE_TYPE', 'EC2_UBUNTU')

vpn_container_name = 'gluetun'

ns = api.namespace('monitor', description='Monitoring operations')

# Define models
disk_usage_model = api.model('DiskUsage', {
    'label': fields.String(description='Label of the disk usage information'),
    'size': fields.String(description='Total size of the filesystem'),
    'used': fields.String(description='Used space on the filesystem'),
    'available': fields.String(description='Available space on the filesystem'),
    'percent': fields.Float(description='Used space percentage'),
})

usage_model = api.model('Usage', {
    'label': fields.String(description='Label for CPU or Memory usage'),
    'number': fields.Float(description='Usage percentage')
})

items_model = api.model('Items', {
    'label': fields.String(description='Label for the system item'),
    'number': fields.String(description='Value of the system item')
})

system_model = api.model('SystemInfo', {
    'isMainServer': fields.Boolean(description='Indicates if the system is the main server'),
    'isRunning': fields.Boolean(description='Indicates if the system is currently running'),
    'items': fields.List(fields.Nested(items_model), description='System items such as uptime, upload speed, etc.'),
    'usage': fields.List(fields.Nested(usage_model), description='CPU and memory usage details'),
    'disk_usage': fields.List(fields.Nested(disk_usage_model), description='Disk usage details')
})

docker_model = api.model('DockerStats', {
    'container_name': fields.String(required=True, description='Container name'),
    'cpu_usage': fields.String(required=True, description='CPU usage percentage'),
    'memory_usage': fields.String(required=True, description='Memory usage percentage')
})

env_model = api.model('Env', {
    'env': fields.String(required=True, description='Environment variables content')
})

env_update_model = api.model('EnvUpdate', {
    'MYSQL_ROOT_PASSWORD': fields.String(description='MySQL root password'),
    'MYSQL_DATABASE': fields.String(description='MySQL database name'),
    'MYSQL_USER': fields.String(description='MySQL username'),
    'MYSQL_PASSWORD': fields.String(description='MySQL user password')
})

service_operation_model = api.model('ServiceOperation', {
    'folder_name': fields.String(required=True, description='Name of the folder containing the project'),
    'operation': fields.String(required=True, description='Operation to perform',
                               enum=['stop', 'restart', 'start', 'update'])
})

service_restart_model = api.model('ServiceRestart', {
    'service': fields.String(required=True, description='Service to restart (e.g., server, db, redis)')
})

service_stop_model = api.model('ServiceStop', {
    'service': fields.String(required=True, description='Service to stop (e.g., server, db, redis)')
})

# Define models
url_test_model = api.model('UrlTest', {
    'url': fields.String(required=True, description='URL to test'),
    'use_vpn': fields.Boolean(description='Use VPN for the request', default=True)
})

vpn_control_model = api.model('VpnControl', {
    'action': fields.String(required=True, description='Action to perform on VPN container',
                            enum=['start', 'stop', 'restart', 'switch']),
    'server': fields.String(description='Optional server name for switching')
})


def get_size(size_in_bytes):
    # Convert size from bytes to a human-readable format
    size_units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    size = size_in_bytes
    while size > 1024 and index < len(size_units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f} {size_units[index]}"


def get_system_info():
    try:
        uptime_days, uptime_hours, uptime_minutes = calculate_uptime(system_start_time)
        system_up_time = f"{uptime_days}D {uptime_hours}H {uptime_minutes}M"

        status = parse_status_file("/home/redbull/reports/system_network_usage.json")

        drive_labels = {
            '/host_fs': 'OS Partition',
            '/host_fs/home': 'Home Partition',
            '/host_fs/mnt/newdrive': 'New Drive'
        }

        if 'No file' not in status:
            result = {
                "isMainServer": system_type == 'Main Server',
                "isRunning": True,
                "items": [
                    {"label": "Uptime", "number": system_up_time},
                    {"label": "Upload", "number": status.get('current_upload_speed', '0 B/s')},
                    {"label": "Download", "number": status.get('current_download_speed', '0 B/s')},
                    {"label": "Downloaded", "number": status.get('instance_total_download', '0 KB')},
                    {"label": "Uploaded", "number": status.get('instance_total_upload', '0 KB')},
                    {"label": "Total", "number": status.get('monthly_total_bandwidth_used', '0 GB')}
                ],
                "usage": [
                    {"label": "CPU Usage", "number": status.get('cpu_percent', 0.0)},
                    {"label": "Memory Usage", "number": status.get('memory_percent', 0.0)}
                ],
            }

            disk_usage = []
            seen = set()
            relevant_mount_points = ['/host_fs', '/host_fs/home', '/host_fs/mnt/newdrive']

            for part in psutil.disk_partitions():
                if part.mountpoint in relevant_mount_points and part.mountpoint not in seen:
                    seen.add(part.mountpoint)
                    usage = psutil.disk_usage(part.mountpoint)
                    label = drive_labels.get(part.mountpoint, 'Partition')
                    disk_usage.append({
                        "label": label,
                        "size": get_size(usage.total),
                        "used": get_size(usage.used),
                        "available": get_size(usage.free),
                        "percent": usage.percent
                    })
            if disk_usage:
                result["disk_usage"] = disk_usage
            return result
        else:
            logger.info(f"No data is returned and {status}")
            return {'message': 'No data available'}, 204
    except Exception as e:
        logger.info(f"Exception occurred: {e}")
        return {'message': str(e)}, 500


def get_docker_stats():
    try:
        containers = client.containers.list()
        stats = []
        for container in containers:
            container_stats = container.stats(stream=False)
            cpu_stats = container_stats['cpu_stats']
            precpu_stats = container_stats['precpu_stats']
            cpu_usage = cpu_stats['cpu_usage']
            percpu_usage = cpu_usage.get('percpu_usage', [cpu_usage['total_usage']])

            if 'system_cpu_usage' in cpu_stats and 'system_cpu_usage' in precpu_stats:
                cpu_delta = cpu_usage['total_usage'] - precpu_stats['cpu_usage']['total_usage']
                system_cpu_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
                number_cpus = len(percpu_usage)
                cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0 if system_cpu_delta > 0 else 0.0
            else:
                cpu_percent = 0.0

            memory_stats = container_stats['memory_stats']
            memory_usage = (memory_stats['usage'] / memory_stats['limit']) * 100.0 if memory_stats['limit'] > 0 else 0.0

            stats.append({
                'container_name': container.name,
                'cpu_usage': f"{cpu_percent:.2f}%",
                'memory_usage': f"{memory_usage:.2f}%"
            })
        return stats
    except docker.errors.DockerException as e:
        return {'message': 'Docker error: ' + str(e)}, 500
    except Exception as e:
        return {'message': 'An error occurred: ' + str(e)}, 500


@ns.route('/system')
class SystemInfo(Resource):
    @ns.doc('get_system_info', description="Retrieve system information including CPU, memory, and disk usage.")
    @ns.marshal_with(system_model)
    def get(self):
        """
        Get the current system statistics.

        This endpoint provides detailed information about the CPU usage, memory usage, and disk usage of the system.
        """
        return get_system_info()


@ns.route('/docker')
class DockerInfo(Resource):
    @ns.doc('get_docker_info', description="Retrieve Docker container stats including CPU and memory usage.")
    @ns.marshal_with(docker_model, as_list=True)
    def get(self):
        """
        Get the current Docker container statistics.

        This endpoint provides information about running Docker containers, including CPU and memory usage.
        """
        return get_docker_stats()


@ns.route('/restart')
class RestartService(Resource):
    @ns.doc('restart_service', description="Restart the server, database, or Redis service.")
    @ns.expect(service_restart_model)
    def post(self):
        """
        Restart the specified service.

        - **server**: Reboots the entire server.
        - **db**: Restarts the MariaDB container.
        - **redis**: Restarts the Redis container.

        If the specified service is not valid, an error message will be returned.
        """
        service = request.json.get('service')
        try:
            if service == 'server':
                subprocess.run(['reboot'])
            elif service == 'db':
                client.containers.get('mariadb').restart()
            elif service == 'redis':
                client.containers.get('redis').restart()
            else:
                if client.containers.get(service):
                    client.containers.get(service).restart()
                else:
                    return {'message': f'{service} is not a valid container name to restart'}, 400
            return jsonify({'status': 'success'})
        except docker.errors.DockerException as e:
            return {'message': 'Docker error: ' + str(e)}, 500
        except Exception as e:
            return {'message': 'An error occurred: ' + str(e)}, 500


@ns.route('/stop')
class StopService(Resource):
    @ns.doc('stop_service', description="Stop the server, database, or Redis service.")
    @ns.expect(service_stop_model)
    def post(self):
        """
        Stop the specified service.

        - **server**: Shuts down the entire server.
        - **db**: Stops the MariaDB container.
        - **redis**: Stops the Redis container.

        If the specified service is not valid, an error message will be returned.
        """
        service = request.json.get('service')
        try:
            if service == 'server':
                subprocess.run(['shutdown', '-h', 'now'])
            elif service == 'db':
                client.containers.get('mariadb').stop()
            elif service == 'redis':
                client.containers.get('redis').stop()
            else:
                if client.containers.get(service):
                    client.containers.get(service).stop()
                else:
                    return {'message': f'{service} is not a valid container name to stop'}, 400
            return jsonify({'status': 'success'})
        except docker.errors.DockerException as e:
            return {'message': 'Docker error: ' + str(e)}, 500
        except Exception as e:
            return {'message': 'An error occurred: ' + str(e)}, 500


@ns.route('/env')
class ManageEnv(Resource):
    @ns.doc('get_env', description="Retrieve the contents of the environment variables file.")
    @ns.marshal_with(env_model)
    def get(self):
        """
        Get the current environment variables.

        This endpoint returns the content of the environment variables file. If the file does not exist, a 404 error is returned.
        """
        env_file = f'{home}/secrets/.env'
        if not os.path.exists(env_file):
            return {'env': 'No environment file found.'}, 404
        with open(env_file, 'r') as file:
            env_data = file.read()
        return {'env': env_data}

    @ns.doc('update_env', description="Update the environment variables file with new values.")
    @ns.expect(env_update_model)
    def post(self):
        """
        Update the environment variables.

        This endpoint allows updating the environment variables in the `.env` file. If relevant database credentials are updated, the changes will be applied to the database as well.
        """
        new_env = request.json
        env_file = f'{home}/secrets/.env'

        # Load existing environment variables
        existing_env = {}
        if os.path.exists(env_file):
            with open(env_file, 'r') as file:
                for line in file:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        existing_env[key] = value

        # Update only the provided environment variables
        for key, value in new_env.items():
            if key in env_update_model.keys() and value:
                existing_env[key] = value

        # Write updated environment variables back to the .env file
        with open(env_file, 'w') as file:
            for key, value in existing_env.items():
                file.write(f'{key}={value}\n')

        # Apply changes to the database if relevant variables are updated
        if {'MYSQL_ROOT_PASSWORD', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD'} & new_env.keys():
            update_db_credentials(new_env)

        return jsonify({'status': 'success'})


@ns.route('/service')
class ServiceOperation(Resource):
    @ns.doc('service_operation', description="Perform operations on a service such as stop, restart, start, or update.")
    @ns.expect(service_operation_model)
    def post(self):
        """
        Perform an operation on a service.

        This endpoint allows performing operations such as stopping, restarting, starting, or updating a service. The `folder_name` must be provided to identify the service to operate on.
        """
        folder_name = request.json.get('folder_name')
        operation = request.json.get('operation')
        service_directory = f"{home}/GIT/{folder_name}"

        if 'server_setup' in folder_name:
            return {'message': f'Directory {folder_name} This folder is not supported.'}, 400

        if not os.path.isdir(service_directory):
            return {'message': f'Directory {folder_name} does not exist.'}, 400

        try:
            result = subprocess.run([f'{home}/server_setup/manage_service.sh', folder_name, operation], check=True,
                                    capture_output=True)
            output = result.stdout.decode() + result.stderr.decode()
            return jsonify({'status': 'success', 'output': output})
        except subprocess.CalledProcessError as e:
            return {'message': e.stderr.decode()}, 500


# VPN Health Check Endpoint
@ns.route('/vpn/health')
class VpnHealthCheck(Resource):
    @ns.doc('vpn_health_check', description="Check the health of the VPN container.")
    def get(self):
        """
        Check if the VPN container is running and healthy.
        """
        try:
            vpn_container = client.containers.get(vpn_container_name)
            health_status = vpn_container.attrs['State']['Health']['Status'] if 'Health' in vpn_container.attrs[
                'State'] else 'Unknown'
            return jsonify({'status': health_status, 'running': vpn_container.status == 'running'})
        except docker.errors.NotFound:
            return jsonify({'status': 'Container not found', 'running': False}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500


# VPN Control (start, stop, restart, switch)
@ns.route('/vpn/control')
class VpnControl(Resource):
    @ns.doc('vpn_control', description="Control the VPN container (start, stop, restart, switch).")
    @ns.expect(vpn_control_model)
    def post(self):
        """
        Control the VPN container by starting, stopping, restarting, or switching servers.
        """
        action = request.json.get('action')
        server = request.json.get('server', None)
        try:
            vpn_container = client.containers.get(vpn_container_name)
            if action == 'start':
                vpn_container.start()
                return {'message': 'VPN started'}, 200
            elif action == 'stop':
                vpn_container.stop()
                return {'message': 'VPN stopped'}, 200
            elif action == 'restart':
                vpn_container.restart()
                return {'message': 'VPN restarted'}, 200
            elif action == 'switch':
                if not server:
                    return {'message': 'Server name is required for switching'}, 400
                # Modify environment and restart the container to switch servers
                vpn_container.stop()
                vpn_container.reload()
                vpn_container.update(environment={'SERVER_COUNTRIES': server})
                vpn_container.start()
                return {'message': f'VPN switched to server: {server}'}, 200
            else:
                return {'message': 'Invalid action'}, 400
        except docker.errors.NotFound:
            return {'message': 'VPN container not found'}, 404
        except Exception as e:
            return {'message': str(e)}, 500


# Proxy URL Request with Optional VPN
@ns.route('/vpn/test-url')
class VpnTestUrl(Resource):
    @ns.doc('vpn_test_url', description="Test a URL with an option to use the VPN proxy.")
    @ns.expect(url_test_model)
    def post(self):
        """
        Test a URL by either routing it through the VPN proxy or bypassing it.
        """
        url = request.json.get('url')
        use_vpn = request.json.get('use_vpn', True)
        # Define common headers like User-Agent, Accept-Language, etc.
        common_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,"
                      "*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            if use_vpn:
                # Make request using the VPN proxy
                proxies = {'http': 'http://gluetun:8888', 'https': 'http://gluetun:8888'}
                response = requests.get(url, headers=common_headers, proxies=proxies)
            else:
                # Make request without VPN
                response = requests.get(url, headers=common_headers)
            # Get content type from the response
            content_type = response.headers.get('Content-Type', '').lower()

            # Dynamically handle the content based on content type
            if 'application/json' in content_type:
                content = response.json()
            elif 'text/plain' in content_type:
                content = response.text
            elif 'text/html' in content_type:
                content = response.text
            else:
                content = response.content  # Return raw content if the type is unknown

            return {'url': url, 'status_code': response.status_code, 'content': content}, 200
        except requests.RequestException as e:
            return {'error': str(e)}, 500


@ns.route('/health')
class HealthCheck(Resource):
    @ns.doc('healthcheck')
    def get(self):
        return jsonify({'status': 'healthy'})


def update_db_credentials(new_env):
    mariadb_container = client.containers.get('mariadb')
    mariadb_container.exec_run(
        f"mysql -u root -p {new_env['MYSQL_ROOT_PASSWORD']} -e \"ALTER USER '{new_env['MYSQL_USER']}'@'%' IDENTIFIED BY '{new_env['MYSQL_PASSWORD']}';\""
    )
    mariadb_container.restart()


# # Store active streams (stream_id -> stream details)
# active_streams = {}
#
#
# class StreamBuffer:
#     def __init__(self):
#         self.buffer = deque()
#         self.lock = threading.Lock()
#
#     def append(self, data):
#         with self.lock:
#             self.buffer.append(data)
#
#     def get_chunk(self):
#         with self.lock:
#             if self.buffer:
#                 return self.buffer.popleft()
#             return None
#
#
# def start_ffmpeg(stream_id, stream_url):
#     """Starts an FFmpeg process for a given stream_id and URL with error handling."""
#     ffmpeg_command = [
#         'ffmpeg', '-re', '-i', stream_url,
#         '-c:v', 'copy', '-c:a', 'aac',  # Use AAC for audio
#         '-b:a', '128k',  # Set audio bitrate
#         '-f', 'mpegts',
#         '-fflags', 'nobuffer',
#         '-flush_packets', '1',
#         'pipe:1'
#     ]
#
#     process = subprocess.Popen(
#         ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10 ** 6
#     )
#
#     # Initialize stream buffer
#     active_streams[stream_id] = {
#         'process': process,
#         'clients': defaultdict(lambda: {'buffer': StreamBuffer(), 'active': True}),
#         'stop': False,
#         'last_chunk_time': time.time()  # Track when the last chunk was received
#     }
#
#     def monitor_process():
#         """Monitor FFmpeg process and restart if it crashes or exits."""
#         while stream_id in active_streams and not active_streams[stream_id]['stop']:
#             try:
#                 stderr_output = active_streams[stream_id]['process'].stderr.readline()
#                 if stderr_output:
#                     logger.error(f"FFmpeg error in stream {stream_id}: {stderr_output.decode()}")
#                     if "Error" in stderr_output.decode():
#                         logger.info(f"Restarting FFmpeg for stream {stream_id} due to an error.")
#                         cleanup_stream(stream_id)
#                         start_ffmpeg(stream_id, active_streams[stream_id]['url'])
#                         return
#             except KeyError:
#                 logger.info(f"Stream {stream_id} has already been stopped and removed.")
#                 break
#         logger.info(f"Exiting monitor process for stream {stream_id}.")
#
#     def read_stream():
#         """Read the FFmpeg process output and distribute to clients."""
#         try:
#             while not active_streams[stream_id]['stop']:
#                 chunk = process.stdout.read(4096)
#                 if not chunk:
#                     logger.info(f"Source stream ended for {stream_id}. Stopping restream.")
#                     break
#
#                 active_streams[stream_id]['last_chunk_time'] = time.time()  # Update the last received chunk time
#
#                 # Append chunk to all active clients
#                 for client_data in list(active_streams[stream_id]['clients'].values()):
#                     if client_data['active']:
#                         client_data['buffer'].append(chunk)
#
#                 # Timeout detection - Restart the process if no data is received for a while
#                 if time.time() - active_streams[stream_id]['last_chunk_time'] > 10:
#                     logger.warning(f"Stream {stream_id} timed out. Restarting.")
#                     cleanup_stream(stream_id)
#                     start_ffmpeg(stream_id, stream_url)
#                     return
#         except Exception as e:
#             logger.error(f"Error while reading stream {stream_id}: {e}")
#         finally:
#             cleanup_stream(stream_id)
#
#     threading.Thread(target=read_stream, daemon=True).start()
#     threading.Thread(target=monitor_process, daemon=True).start()
#     return process
#
#
# def cleanup_stream(stream_id):
#     """Ensures proper cleanup of FFmpeg process and resources."""
#     try:
#         if stream_id in active_streams:
#             logger.info(f"Cleaning up stream {stream_id}")
#             active_streams[stream_id]['stop'] = True  # Signal all threads to stop
#
#             process = active_streams[stream_id]['process']
#             process.kill()  # Ensure the FFmpeg process is stopped
#
#             # Allow threads to exit before deleting the stream entry
#             time.sleep(1)
#
#             # Ensure the stream is removed after threads have safely exited
#             del active_streams[stream_id]
#             logger.info(f"Stream {stream_id} fully terminated.")
#     except Exception as e:
#         logger.error(f"Stream was already deleted.. {stream_id}: {e}")
#
#
# @ns.route('/restream/<stream_id>/<username>')
# class Restream(Resource):
#     @ns.doc('restream')
#     def get(self, stream_id, username):
#         logger.info(f"Stream starting for: {stream_id}, User: {username}")
#
#         # Get stream URL (fallback to default test stream)
#         stream_url = request.args.get('url', "http://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8")
#         if not stream_url:
#             return {"error": "stream_url is required"}, 400
#
#         # Start FFmpeg if the stream is not already active
#         if stream_id not in active_streams:
#             start_ffmpeg(stream_id, stream_url)
#
#         # Handle client-specific data
#         client_data = active_streams[stream_id]['clients'][username]
#
#         # Mark the client as active
#         client_data['active'] = True
#
#         # Clear buffer and reset on reconnect to prevent old chunks from being sent
#         if 'buffer' in client_data:
#             logger.info(f"Clearing buffer for user {username} on reconnect")
#             client_data['buffer'] = StreamBuffer()
#         else:
#             client_data['buffer'] = StreamBuffer()
#
#         process = active_streams[stream_id]['process']
#
#         def generate():
#             while True:
#                 chunk = client_data['buffer'].get_chunk()
#                 if chunk:
#                     yield chunk
#                 else:
#                     time.sleep(0.1)
#
#         # Response with generated stream data
#         response = Response(generate(), content_type='video/mp2t')
#
#         @response.call_on_close
#         def on_close():
#             # Handle client disconnection
#             client_data['active'] = False
#             logger.info(f"Client {username} disconnected from stream {stream_id}")
#
#             # Fully clean up client if no more clients are active
#             if all(not c['active'] for c in active_streams[stream_id]['clients'].values()):
#                 logger.info(f"No more clients active. Stopping stream {stream_id}")
#                 cleanup_stream(stream_id)
#             else:
#                 # Additional safeguard to remove client-specific data
#                 if username in active_streams[stream_id]['clients']:
#                     logger.info(f"Cleaning up user {username} data for stream {stream_id}")
#                     del active_streams[stream_id]['clients'][username]
#
#         return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

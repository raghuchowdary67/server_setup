from flask import Flask, jsonify, request
import psutil
import os
import subprocess
import docker
from flask_restx import Api, Resource, fields

app = Flask(__name__)
api = Api(app, version='1.0', title='System Monitoring API',
          description='A simple API to monitor system and Docker container stats')

client = docker.from_env()
home = "/home/redbull"

ns = api.namespace('monitor', description='Monitoring operations')

system_model = api.model('SystemInfo', {
    'cpu_usage': fields.Float(required=True, description='CPU usage percentage'),
    'memory_usage': fields.Float(required=True, description='Memory usage percentage'),
    'disk_usage': fields.List(fields.Nested(api.model('DiskUsage', {
        'filesystem': fields.String(description='Filesystem name'),
        'size': fields.String(description='Total size of the filesystem'),
        'used': fields.String(description='Used space on the filesystem'),
        'available': fields.String(description='Available space on the filesystem'),
        'percent': fields.Float(description='Used space percentage'),
        'mounted_on': fields.String(description='Mount point of the filesystem'),
    })), description='Disk usage details')
})

docker_model = api.model('DockerStats', {
    'container_name': fields.String(required=True, description='Container name'),
    'cpu_usage': fields.String(required=True, description='CPU usage percentage'),  # Changed to String
    'memory_usage': fields.String(required=True, description='Memory usage percentage')  # Changed to String
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
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_usage = memory.percent
    disk_usage = []

    # Get unique mountpoints for filtering duplicates
    seen = set()
    relevant_mountpoints = ['/host_fs', '/host_fs/home', '/host_fs/mnt/newdrive']

    for part in psutil.disk_partitions():
        if part.mountpoint in relevant_mountpoints and part.mountpoint not in seen:
            seen.add(part.mountpoint)
            usage = psutil.disk_usage(part.mountpoint)
            disk_usage.append({
                'filesystem': part.device,
                'size': get_size(usage.total),
                'used': get_size(usage.used),
                'available': get_size(usage.free),
                'percent': usage.percent,
                'mounted_on': part.mountpoint
            })
    return {
        'cpu_usage': cpu_usage,
        'memory_usage': memory_usage,
        'disk_usage': disk_usage
    }


def get_docker_stats():
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
            'cpu_usage': f"{cpu_percent:.2f}%",  # Format CPU usage as a percentage
            'memory_usage': f"{memory_usage:.2f}%"  # Format memory usage as a percentage
        })
    return stats


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
    @ns.doc("This endpoint allows restarting the server, database, or Redis cache.")
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


@ns.route('/stop')
class StopService(Resource):
    @ns.doc("This endpoint allows stopping the server, database, or Redis cache.")
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
        if service == 'server':
            subprocess.run(['shutdown', 'now'])
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

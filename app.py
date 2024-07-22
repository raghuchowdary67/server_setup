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

ns = api.namespace('monitor', description='Monitoring operations')

system_model = api.model('SystemInfo', {
    'cpu_usage': fields.Float(required=True, description='CPU usage percentage'),
    'memory_usage': fields.Float(required=True, description='Memory usage percentage'),
    'disk_usage': fields.Raw(required=True, description='Disk usage details')
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
    'MYSQL_ROOT_PASSWORD': fields.String(required=True, description='MySQL root password'),
    'MYSQL_DATABASE': fields.String(required=True, description='MySQL database name'),
    'MYSQL_USER': fields.String(required=True, description='MySQL username'),
    'MYSQL_PASSWORD': fields.String(required=True, description='MySQL user password')
})

service_operation_model = api.model('ServiceOperation', {
    'folder_name': fields.String(required=True, description='Name of the folder containing the project'),
    'operation': fields.String(required=True, description='Operation to perform', enum=['stop', 'restart', 'start', 'update'])
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
    @ns.doc('get_system_info')
    @ns.marshal_with(system_model)
    def get(self):
        return get_system_info()

@ns.route('/docker')
class DockerInfo(Resource):
    @ns.doc('get_docker_info')
    @ns.marshal_with(docker_model, as_list=True)
    def get(self):
        return get_docker_stats()

@ns.route('/restart')
class RestartService(Resource):
    @ns.doc('restart_service')
    @ns.expect(api.model('ServiceRestart', {'service': fields.String(required=True, description='Service to restart')}))
    def post(self):
        service = request.json.get('service')
        if service == 'server':
            subprocess.run(['sudo', 'reboot'])
        elif service == 'db':
            client.containers.get('mariadb').restart()
        elif service == 'redis':
            client.containers.get('redis').restart()
        return jsonify({'status': 'success'})

@ns.route('/env')
class ManageEnv(Resource):
    @ns.doc('get_env')
    @ns.marshal_with(env_model)
    def get(self):
        env_file = '/home/secrets/.env'
        if not os.path.exists(env_file):
            return {'env': 'No environment file found.'}, 404
        with open(env_file, 'r') as file:
            env_data = file.read()
        return {'env': env_data}

    @ns.doc('update_env')
    @ns.expect(env_update_model)
    def post(self):
        new_env = request.json
        env_file = '/home/secrets/.env'
        with open(env_file, 'w') as file:
            for key, value in new_env.items():
                file.write(f'{key}={value}\n')
        update_db_credentials(new_env)
        return jsonify({'status': 'success'})

@ns.route('/service')
class ManageService(Resource):
    @ns.doc('manage_service')
    @ns.expect(service_operation_model)
    def post(self):
        folder_name = request.json.get('folder_name')
        operation = request.json.get('operation')
        service_directory = f"/home/redbull/{folder_name}"

        if not os.path.isdir(service_directory):
            return {'message': f'Directory {service_directory} does not exist.'}, 400

        try:
            result = subprocess.run(['/home/redbull/server_setup/manage_service.sh', folder_name, operation], check=True, capture_output=True)
            output = result.stdout.decode() + result.stderr.decode()
            print("output: "+str(output))
            return jsonify({'status': 'success', 'output': output})
        except subprocess.CalledProcessError as e:
            return {'message': e.stderr.decode()}, 500

def update_db_credentials(new_env):
    mariadb_container = client.containers.get('mariadb')
    mariadb_container.exec_run(f"mysql -uroot -p{new_env['MYSQL_ROOT_PASSWORD']} -e \"ALTER USER '{new_env['MYSQL_USER']}'@'%' IDENTIFIED BY '{new_env['MYSQL_PASSWORD']}';\"")
    mariadb_container.restart()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

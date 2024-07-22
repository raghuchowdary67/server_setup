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
    'cpu_usage': fields.Float(required=True, description='CPU usage percentage'),
    'memory_usage': fields.Float(required=True, description='Memory usage percentage')
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

def get_system_info():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_usage = memory.percent
    disk_usage = {part.mountpoint: psutil.disk_usage(part.mountpoint)._asdict() for part in psutil.disk_partitions()}
    return {
        'cpu_usage': cpu_usage,
        'memory_usage': memory_usage,
        'disk_usage': disk_usage
    }

def get_docker_stats():
    containers = client.containers.list()
    stats = {}
    for container in containers:
        container_stats = container.stats(stream=False)
        cpu_percent = (container_stats['cpu_stats']['cpu_usage']['total_usage'] - container_stats['precpu_stats']['cpu_usage']['total_usage']) / \
                      (container_stats['cpu_stats']['system_cpu_usage'] - container_stats['precpu_stats']['system_cpu_usage']) * \
                      len(container_stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
        memory_usage = container_stats['memory_stats']['usage'] / container_stats['memory_stats']['limit'] * 100.0
        stats[container.name] = {
            'cpu_usage': cpu_percent,
            'memory_usage': memory_usage
        }
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
        return jsonify({'status': 'success'}), 200

@ns.route('/env')
class ManageEnv(Resource):
    @ns.doc('get_env')
    @ns.marshal_with(env_model)
    def get(self):
        env_file = '/home/secrets/.env'
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
        return jsonify({'status': 'success'}), 200

def update_db_credentials(new_env):
    mariadb_container = client.containers.get('mariadb')
    mariadb_container.exec_run(f"mysql -uroot -p{new_env['MYSQL_ROOT_PASSWORD']} -e \"ALTER USER '{new_env['MYSQL_USER']}'@'%' IDENTIFIED BY '{new_env['MYSQL_PASSWORD']}';\"")
    mariadb_container.restart()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

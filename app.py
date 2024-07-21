from flask import Flask, jsonify, request
import psutil
import os
import subprocess
import docker

app = Flask(__name__)

client = docker.from_env()

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

@app.route('/system', methods=['GET'])
def system_info():
    return jsonify(get_system_info())

@app.route('/docker', methods=['GET'])
def docker_info():
    return jsonify(get_docker_stats())

@app.route('/restart', methods=['POST'])
def restart_services():
    service = request.json.get('service')
    if service == 'server':
        subprocess.run(['sudo', 'reboot'])
    elif service == 'db':
        client.containers.get('mariadb').restart()
    elif service == 'redis':
        client.containers.get('redis').restart()
    return jsonify({'status': 'success'}), 200

@app.route('/env', methods=['GET', 'POST'])
def manage_env():
    env_file = '/home/secrets/.env'
    if request.method == 'GET':
        with open(env_file, 'r') as file:
            env_data = file.read()
        return jsonify({'env': env_data})
    elif request.method == 'POST':
        new_env = request.json
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

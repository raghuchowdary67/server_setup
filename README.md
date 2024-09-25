# server_setup

This repository provides the necessary configurations to set up the server.

## Running the Application in Docker

To run this application using Docker, use the following command:

```bash
sudo docker-compose up -d --build
```


Example Usage
Request to Stop a Service
bash
Copy code
curl -X POST "http://<your_server_ip>:5000/monitor/service" -H "Content-Type: application/json" -d '{
  "folder_name": "your_project_folder",
  "operation": "stop"
}'
Request to Restart a Service
bash
Copy code
curl -X POST "http://<your_server_ip>:5000/monitor/service" -H "Content-Type: application/json" -d '{
  "folder_name": "your_project_folder",
  "operation": "restart"
}'
Request to Start a Service
bash
Copy code
curl -X POST "http://<your_server_ip>:5000/monitor/service" -H "Content-Type: application/json" -d '{
  "folder_name": "your_project_folder",
  "operation": "start"
}'
Request to Update a Service
bash
Copy code
curl -X POST "http://<your_server_ip>:5000/monitor/service" -H "Content-Type: application/json" -d '{
  "folder_name": "your_project_folder",
  "operation": "update"
}'


#LOGS

List all running containers:

bash
Copy code
docker ps
This might output something like:

plaintext
Copy code
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS              PORTS                    NAMES
abc123456789        flask_app:latest    "python app.py"          5 minutes ago       Up 5 minutes        0.0.0.0:5000->5000/tcp   flask_app
def234567890        mariadb:10.5        "docker-entrypoint.s…"   5 minutes ago       Up 5 minutes        0.0.0.0:3306->3306/tcp   mariadb
ghi345678901        redis:6             "docker-entrypoint.s…"   5 minutes ago       Up 5 minutes        0.0.0.0:6379->6379/tcp   redis
Find the CONTAINER ID or NAMES for your flask_app container.

View the logs of the Flask application container:

bash
Copy code
docker logs flask_app
Follow the logs in real-time:

bash
Copy code
docker logs -f flask_app
Viewing Logs for All Services in Docker Compose
If you want to view logs for all services defined in your Docker Compose file, you can use the docker-compose logs command.

Navigate to the directory containing your docker-compose.yml file:

bash
Copy code
cd /home/redbull/flask_app
View the logs for all services:

bash
Copy code
sudo docker-compose logs
Follow the logs in real-time:

bash
Copy code
sudo docker-compose logs -f


#Usefull Docker commands
  rm -rf dir-name
  cat $HOME/secrets/.env
  docker inspect --format='{{json .State.Health}}' mariadb
  docker logs -f --tail 10 redbull-admin-backend
  docker exec -it mariadb bash
  docker run -it --rm mariadb:10.5 /bin/bash
  docker exec -it mariadb mysql -u root -p
  docker exec -it mariadb mysql -u redbull_admin -p

# Docker complete reset
To perform all in one command use the below one:
    docker stop $(docker ps -aq) && docker rm $(docker ps -aq) && docker rmi $(docker images -q) && docker volume rm $(docker volume ls -q)
Or else use the individual ones.
  1. Stop and Remove All Containers
     docker stop $(docker ps -aq)
     docker rm $(docker ps -aq)
  2. Remove All Images
     docker rmi $(docker images -q)
  3. Remove All Volumes
     docker volume rm $(docker volume ls -q)
  4. Remove All Networks
     docker network rm $(docker network ls -q)
  5. Remove All Docker Data (Optional)
     sudo systemctl stop docker 
     sudo rm -rf /var/lib/docker
     sudo systemctl start docker

To Refresh the .env files we need to recreate the application:

1. Stop and Remove the Existing Container
Run the following command to stop and remove the existing container:

bash
Copy code
docker-compose stop redbull-admin-backend
docker-compose rm -f redbull-admin-backend
2. Rebuild and Restart the Service
Rebuild and restart the service to ensure it picks up the changes in the .env file:

bash
Copy code
docker-compose up --build -d redbull-admin-backend

To check the ip address of the each docker container use this command
docker ps -q | xargs -I{} sh -c 'docker inspect --format "{{.Name}} - {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" {}'

to clean up old images 

docker rmi $(docker images -q redbull-admin-backend)

start the vpn docker compose:

docker compose -f docker-compose-vpn.yml up --build -d

For server_setup only
docker compose up --build -d server_setup

curl -X 'POST' \
  'http://192.168.1.105:5000/monitor/vpn/test-url' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "url": "http://harnhrt.leadervpn.xyz/player_api.php?username=pavan5544&password=8682783180",
  "use_vpn": true
}'
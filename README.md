# server_setup
This is to setup the server

to run this app in docker use the below command..
sudo docker-compose up -d --build


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
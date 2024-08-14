FROM python:3.8-slim

WORKDIR /app

COPY app.py /app
COPY check_mariadb_health.sh /app

RUN pip install flask psutil docker flask-restx

# Install git and docker-compose
RUN apt-get update && apt-get install -y git curl
RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

# Make the script executable
RUN chmod +x /app/check_mariadb_health.sh

CMD ["python", "app.py"]

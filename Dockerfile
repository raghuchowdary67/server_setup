FROM python:3.8-slim

WORKDIR /app

COPY app.py /app

RUN pip install flask psutil docker flask-restx

# Install git and docker-compose
RUN apt-get update && apt-get install -y git curl
RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

CMD ["python", "-u", "app.py"]
#CMD ["python", "app.py"]

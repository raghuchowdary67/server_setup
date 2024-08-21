FROM python:3.8-slim

# Create a non-root user named 'redbull'
RUN useradd -ms /bin/bash redbull

# Set the working directory and change ownership to the user 'redbull'
WORKDIR /app
COPY --chown=redbull:redbull app.py /app
COPY --chown=redbull:redbull common /app/common

# Install required Python packages
RUN pip install flask psutil docker flask-restx flask-cors

# Install git and docker-compose
RUN apt-get update && apt-get install -y git curl
RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

# Switch to the non-root user
USER redbull

CMD ["python", "app.py"]

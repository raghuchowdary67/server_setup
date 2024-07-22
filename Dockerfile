FROM python:3.8-slim

WORKDIR /app

COPY app.py /app

RUN pip install flask psutil docker flask-restx

CMD ["python", "-u", "app.py"]
#CMD ["python", "app.py"]

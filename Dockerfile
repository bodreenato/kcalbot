FROM python:3.10-slim
LABEL authors="dpogorelov"

COPY . /app
WORKDIR /app
RUN python3 -m pip install -r requirements.txt
ENTRYPOINT ["python3", "main.py"]
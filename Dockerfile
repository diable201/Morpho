FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt /app
COPY main.py /app

RUN apk add --no-cache build-base
RUN pip install -r requirements.txt

CMD ["python", "-u", "main.py"]
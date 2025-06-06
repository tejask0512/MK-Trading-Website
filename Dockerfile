# Use official lightweight Python image
FROM python:3.10-slim


COPY . /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]

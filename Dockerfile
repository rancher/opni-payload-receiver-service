FROM python:3.8-slim
EXPOSE 80
COPY ./payload-receiver-service/app /app
COPY ./payload-receiver-service/requirements.txt /app
WORKDIR "app"
RUN pip install --no-cache-dir -r /app/requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

FROM python:3.8-slim as base

# Build python modules first
FROM base as builder

RUN apt-get update \
    && apt-get install gcc -y \
    && apt-get clean

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./payload-receiver-service/requirements.txt /requirements.txt

RUN pip install -r /requirements.txt

# Create the final image
FROM base
EXPOSE 80

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./payload-receiver-service/app /app

WORKDIR "app"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

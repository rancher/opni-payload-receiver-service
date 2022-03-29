FROM rancher/opni-python-base:3.8

WORKDIR /code

COPY ./opensearch-fetcher/log_fetching_service_cpy.py .

CMD ["python", "./log_fetching_service_cpy.py"]

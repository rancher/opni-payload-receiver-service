# Standard Library
import asyncio
import logging
import os
import time

# Third Party
from datetime import datetime
from elasticsearch import AsyncElasticsearch, TransportError
from opni_nats import NatsWrapper
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")

ES_ENDPOINT = os.environ["ES_ENDPOINT"]
ES_USERNAME = os.environ["ES_USERNAME"]
ES_PASSWORD = os.environ["ES_PASSWORD"]
TIME_RANGE_SECONDS = int(os.getenv("TIME_RANGE_SECONDS", "10"))

nw = NatsWrapper()

async def send_all_results_to_nats(es, start_ts, end_ts):
    scroll_value = "1m"
    es_query_body = {
        "query": {
            "bool": {
                "filter": [{"range": {"time": {"gte": start_ts, "lt": end_ts}}}]
            },
        }
    }

    first_page = True
    while True:
        if first_page:
            current_page = await es.search(index="logs", body=es_query_body, scroll=scroll_value, size=2000)
            first_page = False
        else:
            current_page = await es.scroll(scroll_id=scroll_id, scroll=scroll_value)
        if "_scroll_id" in current_page:
            scroll_id = current_page["_scroll_id"]
            current_page_results = current_page["hits"]["hits"]
            if len(current_page_results) > 0:
                accumulated_results = []
                for result in current_page_results:
                    result_dict = result["_source"].copy()
                    result_dict["_id"] = result["_id"]
                    accumulated_results.append(result_dict)
                accumulated_results_df = pd.DataFrame(accumulated_results)
                logging.info("Published {} logs to Nats now".format(len(accumulated_results)))
                await nw.publish("raw_logs", accumulated_results_df.to_json().encode())
            else:
                break
        else:
            break

async def fetch_logs():
    es = await setup_es_connection()
    query_time = 0
    try:
        current_ts = int((datetime.now().timestamp() - TIME_RANGE_SECONDS) * 1000)
        last_fetched_exists = await es.indices.exists("last_fetched")
        last_fetched_timestamp_results = None
        # On startup, check if index last_fetched already exists.
        if last_fetched_exists:
            last_fetched_timestamp_results = (await es.search(index="last_fetched", body={"query": {"match_all": {}}}))["hits"]["hits"][0]
            last_fetched_timestamp = last_fetched_timestamp_results["_source"]["last_fetched_timestamp"]
            await send_all_results_to_nats(es, last_fetched_timestamp, current_ts)
            await es.update(index="last_fetched", doc_type=last_fetched_timestamp_results["_type"], id=last_fetched_timestamp_results["_id"], body={"doc": {"last_fetched_timestamp": current_ts}})

        while True:
            await asyncio.sleep(TIME_RANGE_SECONDS - min(query_time, TIME_RANGE_SECONDS))
            end_ts = current_ts + (TIME_RANGE_SECONDS * 1000)
            start_time = time.time()
            await send_all_results_to_nats(es, current_ts, end_ts)
            if last_fetched_timestamp_results:
                await es.update(index="last_fetched", doc_type=last_fetched_timestamp_results["_type"], id=last_fetched_timestamp_results["_id"], body={"doc": {"last_fetched_timestamp": end_ts}})
            else:
                await es.index(index="last_fetched", body={"last_fetched_timestamp": end_ts})
            query_time = time.time() - start_time
            current_ts += (TIME_RANGE_SECONDS * 1000)
    except Exception as e:
        logging.error(f"Unable to access Opensearch. {e}")

async def setup_es_connection():
    logging.info("Setting up AsyncElasticsearch")
    return AsyncElasticsearch(
        [ES_ENDPOINT],
        port=9200,
        http_auth=(ES_USERNAME, ES_PASSWORD),
        http_compress=True,
        max_retries=10,
        retry_on_status={100, 400, 503},
        retry_on_timeout=True,
        timeout=20,
        use_ssl=True,
        verify_certs=False,
        sniff_on_start=False,
        # refresh nodes after a node fails to respond
        sniff_on_connection_fail=True,
        # and also every 60 seconds
        sniffer_timeout=60,
        sniff_timeout=10,
    )

async def wait_for_index():
    es = await setup_es_connection()
    while True:
        try:
            exists = await es.indices.exists("logs")
            if exists:
                break
            else:
                logging.info("waiting for logs index")
                time.sleep(2)

        except TransportError as exception:
            logging.info(f"Error in es indices {exception}")
            if exception.status_code == "N/A":
                logging.info("Elasticsearch connection error")
                es = await setup_es_connection()

async def init_nats():
    logging.info("Attempting to connect to NATS")
    await nw.connect()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    log_fetching_coroutine = fetch_logs()

    loop.run_until_complete( asyncio.gather(init_nats(), wait_for_index()))
    log_fetching_task = loop.create_task(log_fetching_coroutine)
    loop.run_until_complete(log_fetching_task)

    try:
        loop.run_forever()
    finally:
        loop.close()

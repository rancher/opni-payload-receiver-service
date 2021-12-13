# Standard Library
import asyncio
import logging
import math

# Third Party
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from nats.aio.client import Client as NATS
from opni_nats import NatsWrapper

app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
nw = None


@app.on_event("startup")
async def startup_event():
    global nw
    nw = NatsWrapper()
    await nw.connect()


async def get_nats() -> NATS:
    if not nw.nc.is_connected:
        await nw.connect()
    return nw.nc


async def push_to_nats(nats: NATS, payload):
    try:
        df = pd.json_normalize(payload)
        if "time" in df.columns:
            df.time.replace(r"^\s*$", np.nan, regex=True, inplace=True)
            df.loc[~df.time.notnull(), "time"] = pd.to_datetime(
                "now", utc=True
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            # normalize time field
            df["time"] = df["time"].astype(str)
            df["time_length"] = df["time"].str.len()
            for group_name, df_group in df.groupby("time_length"):
                # normalize all unix timestamp to ns
                if all(pd.to_numeric(df_group["time"], errors="coerce").notna()):
                    df_group["time"] = df_group["time"].apply(
                        lambda d: int(f"{int(float(d)):0<19d}")
                    )
                    if group_name > 19:
                        df_group["time"] = int(
                            df_group["time"] / (10 ** (group_name - 19))
                        )
                df_group["time"] = pd.to_datetime(
                    df_group["time"], unit="ns", utc=True
                ).dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                for idx, row in df_group.iterrows():
                    df.loc[idx, "time"] = row["time"]
        else:
            df["time"] = pd.to_datetime("now", utc=True).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            logging.info("Setting current UTC time to payload without timestamps")
        df["dt"] = pd.to_datetime(df.time, errors="coerce", utc=True)
        df["time_nanoseconds"] = df["dt"].astype(np.int64)
        # compute window
        df["window_dt"] = df["dt"].dt.floor("60s")
        df["window_start_time_ns"] = df["window_dt"].astype(np.int64)
        df["insights_10min_bin"] = df["dt"].dt.floor("600s").astype(np.int64) // 10 ** 6
        df["insights_30min_bin"] = (
            df["dt"].dt.floor("1800s").astype(np.int64) // 10 ** 6
        )
        df["insights_60min_bin"] = (
            df["dt"].dt.floor("3600s").astype(np.int64) // 10 ** 6
        )
        df["_id"] = df["time_nanoseconds"].map(str) + df.groupby(
            "time_nanoseconds"
        ).cumcount().map("{:016b}".format)
        df.drop(columns=["dt", "time_nanoseconds"], inplace=True)
        df = df.fillna("")
        if "id" in df.columns:
            df["id"] = df["id"].map(str)

        for _, data_df in df.groupby(["window_start_time_ns"]):
            window_payload_size_bytes = data_df.memory_usage(deep=True).sum()
            num_chunked_dfs = max(
                1, math.ceil(window_payload_size_bytes / nats.max_payload)
            )
            if num_chunked_dfs > 1:
                logging.info(
                    "payload_df size = {} bytes. NATS max payload = {} bytes. Chunking into {} DataFrames".format(
                        window_payload_size_bytes, nats.max_payload, num_chunked_dfs
                    )
                )
            # process every chunk
            for chunked_payload_df in np.array_split(data_df, num_chunked_dfs):
                await nats.publish("raw_logs", chunked_payload_df.to_json().encode())

    except Exception as e:
        logging.error(f"Error: {str(e)}")


@app.post("/")
async def index(request: Request):
    logging.info(f"Received request: {str(request)}")
    try:
        logs_payload = await request.json()
        asyncio.create_task(push_to_nats(await get_nats(), logs_payload))
    except:
        # Bad Request
        raise HTTPException(
            status_code=404, detail="Something wrong with request {request}"
        )

# Standard Library
import asyncio
import json
import subprocess
import time
from datetime import datetime
from queue import Queue
from threading import Thread

# Third Party
import requests
from faker import Faker
from nats.aio.client import Client as NATS
from opni_nats import NatsWrapper

nw = NatsWrapper()
fake = Faker()
log_data = ('{"log": {"0":"' + fake.sentence(10) + '"}}')
tr_queue = Queue()

def test_prs_happy_path():
    
    # This test is to verify the happy path functionality of the Payload Receiver Service (PRS). 
    # In this test, we are verifying that each of the following fields are successfully added to a log submitted to the PRS.
        # time
        # window_dt
        # window_start_time_ns
        # _id

    # nats subscribe
    subscribe(tr_queue, log_data)
    
    wait_for_seconds(2)

    print('Sending Dataset')
    r = requests.post("http://opni-svc-payload-receiver.opni.svc.cluster.local:80",
            data=log_data,
            verify=False)
        
    if len(r.content) != 0:
        print(("Request Content: "), r.content)
        print(("Request Headers: "), r.headers)
        print(("Request Status Code"), r.status_code)
        bad_content = '{"detail":"Something wrong with request'
        content = r.content.decode("utf-8")
        if bad_content in content:
            raise Exception("Bad Request sent to API")
        if r.status_code != 200:
            raise Exception("Bad Request sent to API")
    
    wait_for_seconds(2)

    json_payload = tr_queue.get()
    tr_queue.task_done()
    assert json_payload["time"]["0"] != None
    assert json_payload["window_dt"]["0"] != None
    assert json_payload["window_start_time_ns"]["0"] != None
    assert json_payload["_id"]["0"] != None
    empty_queue(tr_queue)


def test_prs_time_assertion():
    
    # This test is to verify the happy path functionality of the time output of the Payload Receiver Service (PRS). 

    # nats subscribe
    subscribe(tr_queue, log_data)
    
    wait_for_seconds(2)

    print('Sending Dataset')
    r = requests.post("http://opni-svc-payload-receiver.opni.svc.cluster.local:80",
            data=log_data,
            verify=False)
        
    if len(r.content) != 0:
        print(("Request Content: "), r.content)
        print(("Request Headers: "), r.headers)
        print(("Request Status Code"), r.status_code)
        bad_content = '{"detail":"Something wrong with request'
        content = r.content.decode("utf-8")
        if bad_content in content:
            raise Exception("Bad Request sent to API")
        if r.status_code != 200:
            raise Exception("Bad Request sent to API")
    
    wait_for_seconds(2)

    json_payload = tr_queue.get()
    tr_queue.task_done()
    now = datetime.now()
    #This should be getting the current time and setting it to be a date/timestamp with the format YYYY-MM-DDTHH:MM:SS
    current_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    #This should only pull in the first 19 characters of the "time""0" value, which should be YYYY-MM-DDTHH:MM:SS
    payload_date = json_payload["time"]["0"][:19]
    #This should be setting the first 19 characters to be a timestamp with the format YYYY-MM-DDTHH:MM:SS
    payload_datetime = datetime.strptime(payload_date, "%Y-%m-%dT%H:%M:%S")
    assert current_datetime >= str(payload_datetime)
    empty_queue(tr_queue)


def test_prs_unique_id():
    
    # This test is to verify the each log submitted to the Payload Receiver Service (PRS) is unique. 
        
    # nats subscribe
    subscribe(tr_queue, log_data)
    
    wait_for_seconds(2)

    log_data1 = ('{"log": {"0":"' + fake.sentence(10) + '"}}')
    print('Sending Dataset 1')
    r = requests.post("http://opni-svc-payload-receiver.opni.svc.cluster.local:80",
            data=log_data1,
            verify=False)
    json_payload_1 = tr_queue.get()
    tr_queue.task_done()
    id_1 = json_payload_1["_id"]["0"]
    print('First ID:', id_1)
    empty_queue(tr_queue)

    if len(r.content) != 0:
        print(("Request Content: "), r.content)
        print(("Request Headers: "), r.headers)
        print(("Request Status Code"), r.status_code)
        bad_content = '{"detail":"Something wrong with request'
        content = r.content.decode("utf-8")
        if bad_content in content:
            raise Exception("Bad Request sent to API")
        if r.status_code != 200:
            raise Exception("Bad Request sent to API")

    wait_for_seconds(5)

    log_data2 = ('{"log": {"0":"' + fake.sentence(10) + '"}}')
    print('Sending Dataset 2')
    r2 = requests.post('http://opni-svc-payload-receiver.opni.svc.cluster.local:80',
            data=log_data2,
            verify=False)
    json_payload_2 = tr_queue.get()
    tr_queue.task_done()
    id_2 = json_payload_2["_id"]["0"]
    print('Second ID:', id_2)
    empty_queue(tr_queue)
        
    if len(r2.content) != 0:
        print(('Request Content: '), r2.content)
        print(('Request Headers: '), r2.headers)
        print(('Request Status Code'), r2.status_code)
        bad_content = '{"detail":"Something wrong with request'
        content = r2.content.decode("utf-8")
        if bad_content in content:
            raise Exception("Bad Request sent to API")
        if r2.status_code != 200:
            raise Exception("Bad Request sent to API")
    
    wait_for_seconds(2)

    assert id_2 != id_1


def test_prs_large_log():
    
    # This test is to verify the Payload Receiver Service (PRS) can handle very large payloads with mulitple logs.

    large_log_data = '[{"log": {"0": "' + fake.sentence(100000) + '"}},\
    {"log": {"1": "' + fake.sentence(100000) + '"}},\
    {"log": {"2": "' + fake.sentence(100000) + '"}},\
    {"log": {"3": "' + fake.sentence(100000) + '"}},\
    {"log": {"4": "' + fake.sentence(100000) + '"}},\
    {"log": {"5": "' + fake.sentence(100000) + '"}},\
    {"log": {"6": "' + fake.sentence(100000) + '"}}]';

    # nats subscribe
    subscribe(tr_queue, large_log_data)
    
    wait_for_seconds(2)

    print('Sending Dataset')
    r = requests.post('http://opni-svc-payload-receiver.opni.svc.cluster.local:80',
            data=large_log_data,
            verify=False)
        
    if len(r.content) != 0:
        print(('Request Content: '), r.content)
        print(('Request Headers: '), r.headers)
        print(('Request Status Code'), r.status_code)
        bad_content = '{"detail":"Something wrong with request'
        content = r.content.decode("utf-8")
        if bad_content in content:
            raise Exception('Bad Request sent to API')
        if r.status_code != 200:
            raise Exception('Bad Request sent to API')
    
    wait_for_seconds(2)

    json_payload = tr_queue.get()
    tr_queue.task_done()
    assert json_payload["time"]["0"] != None
    assert json_payload["window_dt"]["0"] != None
    assert json_payload["window_start_time_ns"]["0"] != None
    assert json_payload["_id"]["0"] != None
    print(json_payload["_id"])
    empty_queue(tr_queue)


def wait_for_seconds(seconds):
    start_time = time.time()
    while time.time() - start_time < seconds:
        continue


def empty_queue(q: asyncio.Queue):
    for _ in range(q.qsize()):
        q.get_nowait()
        q.task_done()


def check_logs(incoming, expected):
    if expected in incoming:
        return True


async def consume_logs(trqueue, logdata):
    async def subscribe_handler(msg):
        sbj = msg.subject
        print('Subscribing to the "' + sbj + '" subject')
        payload_data = msg.data.decode()
        if check_logs(payload_data, logdata):
            trqueue.put(True)
        
        payload = json.loads(payload_data)
        tr_queue.put(payload)

    await nw.subscribe(
        nats_subject="raw_logs",
        subscribe_handler=subscribe_handler,
    )


async def init_nats():
    print("Attempting to connect to NATS")
    await nw.connect()
    assert nw.connect().__init__

def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def subscribe(trqueue, logdata):

    loop = asyncio.get_event_loop()

    nats_consumer_coroutine = consume_logs(trqueue, logdata)

    t = Thread(target=start_background_loop, args=(loop,), daemon=True)
    t.start()

    asyncio.run_coroutine_threadsafe(init_nats(), loop)
    asyncio.run_coroutine_threadsafe(nats_consumer_coroutine, loop)

    return t


def start_process(command):
    try:
        return subprocess.run(command, shell=True)
    except subprocess.CalledProcessError as e:
        return None

from copy import Error
from logging import Handler
from os import dup, environ
from time import sleep

from praw.reddit import Subreddit
from library import scoring
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from multiprocessing import Process, Pipe
from datetime import datetime
from timeit import default_timer, main
import json
import sys
import boto3
import os
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial

from requests import Session, Response
from requests.adapters import HTTPAdapter

if "IS_LAMBDA_AWS" in os.environ and os.environ["IS_LAMBDA_AWS"] == "TRUE":
    client = boto3.client('lambda')

def thread_handler(session, input):
    if "IS_LAMBDA_AWS" in os.environ and os.environ["IS_LAMBDA_AWS"] == "TRUE":
        response = client.invoke(FunctionName = os.environ["AWS_SCORER_FUNCTION_NAME"], InvocationType = 'RequestResponse', Payload = json.dumps(input))
        retval = json.load(response["Payload"])
        #TODO: check response
    else:
        #print("INPUT:", input)
        response = session.post("http://loadbalancer:8024/scorer", json=input)
        #print("RESPONSE", response.content, "\n", "\n")
        #print(response.status_code)
        retval = json.loads(response.content.decode("utf-8"))
        #TODO: check response
    return retval


def parse_input(event):
    if "view" in event:
        view = event['view']
    else:
        view = "top"

    if "n" in event:
        n = event['n']
    else:
        n = 100
    
    if "subreddit" in event:
        subreddit_name = event["subreddit"]
    else:
        subreddit_name = "news"

    if "time_filter" in event:
        time_filter = event["time_filter"]
    else:
        time_filter = "all"
    
    return view, n, subreddit_name, time_filter


def thread_pool_execute(iterables, method, pool_size) -> list:
    """Multiprocess requests, returns list of responses."""
    session = Session()
    session.mount('https://', HTTPAdapter(pool_maxsize=pool_size))  # that's it
    session.mount('http://', HTTPAdapter(pool_maxsize=pool_size))  # that's it    
    worker = partial(method, session)
    with ThreadPoolExecutor(pool_size) as pool:
        results = pool.map(worker, iterables)
    session.close()
    return list(results)


def record_metrics(db, monitoring_object, start_time, end_time, error):
    monitoring_object["ellapsed_milliseconds"] = int((end_time-start_time)*1000)
    if error:
        monitoring_object["error"] = error
    db.monitoring.insert_one(monitoring_object)


def lambda_handler(event, context):
    view, n, subreddit_name, time_filter = parse_input(event)
    threadpool_size = int(os.environ["RETRIEVER_THREADPOOL_SIZE"]) if "RETRIEVER_THREADPOOL_SIZE" in os.environ and os.environ["RETRIEVER_THREADPOOL_SIZE"] != "" else 100
    monitoring_object = {"view": view, "n": n, "subreddit_name": subreddit_name, "time_filter": time_filter, "platform": "AWS Lambda" if "IS_LAMBDA_AWS" in os.environ and os.environ["IS_LAMBDA_AWS"] == "TRUE" else "Docker Compose", "request_time": str(datetime.now()), "error": "None"}
    if "MONGODB_CONNECTION_URL" in os.environ:
        client = MongoClient(os.environ["MONGODB_CONNECTION_URL"])
    else:
        raise Exception("Environment variable MONGODB_CONNECTION_URL not set")
    db = client.factmata_interview
    start_time = default_timer()
    try:
        counter = 0
        urls = scoring.get_urls(view, time_filter, n, subreddit_name)
        signals = scoring.get_signals_list()
        inputs = []
        scores = []
        error = None
        with ThreadPoolExecutor(threadpool_size) as pool:
            texts = pool.map(scoring.get_text, urls)
        for url,text in zip(urls, texts):
            if text is None: #It means the article could not be downloaded for legal reasons or was otherwise inaccessible
                continue
            counter += 1
            for signal in signals:
                inputs.append({"url": url, "signal": signal, "text": text})
        scores = thread_pool_execute(inputs, thread_handler, threadpool_size)
        monitoring_object["readable_links"] = counter
    except Exception as e:
        raise e
        error = str(type(e))
        monitoring_object["error_message"] = str(e)
    try:
        if scores and not error:
            monitoring_object["calculated_scores"] = len(scores)
            db.scores.insert_many(scores, ordered=False)
    except BulkWriteError:
        print("Duplicate url(s) found")
    end_time = default_timer()
    record_metrics(db, monitoring_object, start_time, end_time, error)
    return {"Outcome": "Success" if error is None else error + " Error"}

def main():
    if len(sys.argv) < 5:
        raise Error("Wrong parameters. The program should be called with the following parameters, in this order: view, n, subreddit_name, time_filter")
    view = sys.argv[1]
    n = int(sys.argv[2])
    subreddit_name = sys.argv[3]
    time_filter = sys.argv[4]
    lambda_handler({"view": view, "n": n, "subreddit": subreddit_name, "time_filter": time_filter}, None)

if __name__ == "__main__":
    main()

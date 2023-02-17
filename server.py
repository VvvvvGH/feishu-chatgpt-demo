#!/usr/bin/env python3.8
import json
import os
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from revChatGPT.V1 import Chatbot

from api import MessageApiClient
from event import MessageReceiveEvent, UrlVerificationEvent, EventManager
from flask import Flask, jsonify
from dotenv import load_dotenv, find_dotenv

# load env parameters form file named .env
load_dotenv(find_dotenv())

app = Flask(__name__)

# load from env
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY")
LARK_HOST = os.getenv("LARK_HOST")

# init service
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()

chatbot = Chatbot(config={
    "email": os.getenv("EMAIL"),
    "password": os.getenv("PASSWORD")
})

executor = ThreadPoolExecutor(10)


@event_manager.register("url_verification")
def request_url_verify_handler(req_data: UrlVerificationEvent):
    # url verification, just need return challenge
    if req_data.event.token != VERIFICATION_TOKEN:
        raise Exception("VERIFICATION_TOKEN is invalid")
    return jsonify({"challenge": req_data.event.challenge})


@event_manager.register("im.message.receive_v1")
def message_receive_event_handler(req_data: MessageReceiveEvent):
    sender_id = req_data.event.sender.sender_id
    open_id = sender_id.open_id

    message = req_data.event.message
    if message.message_type != "text":
        logging.warning("Other types of messages have not been processed yet")
        send("ERROR：仅支持文本消息", open_id)
        return jsonify()
    else:
        query = json.loads(message.content)['text']

    print("submit query =" + query)
    # do_resp_ai(query, open_id)
    executor.submit(do_resp_ai, query, open_id)

    return jsonify()


def do_resp_ai(query, open_id):
    print("execute query=" + query)
    prev_text = ""
    temp = ""
    for data in chatbot.ask(query, ):
        message = data["message"][len(prev_text):]
        print(message, end="", flush=True)
        temp += message
        if temp.endswith("\n\n") and not temp.startswith("```"):
            msg = temp.strip('\n').replace('\n\n', '\n')
            send(msg, open_id)
            temp = ""
        if temp.startswith("```") and temp.endswith("```\n\n"):
            msg = temp
            send(msg, open_id)
            temp = ""
        prev_text = data["message"]
    msg = temp.strip('\n').replace('\n\n', '\n')
    send(msg, open_id)


def send(resp, open_id):
    if len(resp) > 0:
        response = {'text': resp}
        # print("response=" + resp)
        message_api_client.send_text_with_open_id(open_id, json.dumps(response))


@app.errorhandler
def msg_error_handler(ex):
    logging.error(ex)
    response = jsonify(message=str(ex))
    response.status_code = (
        ex.response.status_code if isinstance(ex, requests.HTTPError) else 500
    )
    return response


@app.route("/", methods=["POST"])
def callback_event_handler():
    # init callback instance and handle
    event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN, ENCRYPT_KEY)

    return event_handler(event)


if __name__ == "__main__":
    # init()
    app.run(host="0.0.0.0", port=3000, debug=False)

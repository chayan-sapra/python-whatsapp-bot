import logging
import json
import requests
from flask import Blueprint, request, jsonify, current_app

from .decorators.security import signature_required
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,
    send_message
    )
from .utils.constants import *

webhook_blueprint = Blueprint("webhook", __name__)

class AppointmentBookingBot:
    def __init__(self):
        self.user_states = {}

    def initialize_user(self, mobile_number):
        self.user_states[mobile_number] = {
            "step": 0,
            "details": {
                "name": None,
                "date": None,
                "time": None,
            }
        }

    def get_next_message(self, mobile_number, response=None):
        if mobile_number not in self.user_states:
            self.initialize_user(mobile_number)

        user_state = self.user_states[mobile_number]
        step = user_state["step"]
        details = user_state["details"]

        if step == 0:
            user_state["step"] += 1
            return self.send_ask_name_message(mobile_number)
        elif step == 1:
            details["name"] = response
            user_state["step"] += 1
            return self.send_ask_date_message(mobile_number)
        elif step == 2:
            details["date"] = response
            user_state["step"] += 1
            return self.send_ask_time_message(mobile_number)
        elif step == 3:
            details["time"] = response
            user_state["step"] += 1
            return self.confirm_appointment(mobile_number, details)
        else:
            return self.confirm_appointment(mobile_number, details)


    def send_ask_name_message(self, mobile_number):
        return json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": mobile_number,
            "type": "text",
            "text": {
                "body": "Please provide your full name for the appointment booking."
            }
        })

    def send_ask_date_message(self, mobile_number):
        return json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": mobile_number,
            "type": "text",
            "text": {
                "body": "Please provide your preferred date for the appointment (e.g., 2024-06-15)."
            }
        })

    def send_ask_time_message(self, mobile_number):
        return json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": mobile_number,
            "type": "text",
            "text": {
                "body": "Please provide your preferred time for the appointment (e.g., 10:00 AM)."
            }
        })

    def confirm_appointment(self, mobile_number, details):
        confirmation_message = (
            f"Thank you, {details['name']}! "
            f"Your appointment is scheduled for {details['date']} at {details['time']}."
        )
        return json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": mobile_number,
            "type": "text",
            "text": {
                "body": confirmation_message
            }
        })


bot = AppointmentBookingBot()

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def handle_message():
    """
    Handle incoming webhook events from the WhatsApp API.

    This function processes incoming WhatsApp messages and other events,
    such as delivery statuses. If the event is a valid message, it gets
    processed. If the incoming payload is not a recognized WhatsApp event,
    an error is returned.

    Every message send will trigger 4 HTTP requests to your webhook: message, sent, delivered, read.

    Returns:
        response: A tuple containing a JSON response and an HTTP status code.
    """
    body = request.get_json()
    logging.info(f"request body: {body}")

    # Check if it's a WhatsApp status update
    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")
    ):
        logging.info("Received a WhatsApp status update.")
        return jsonify({"status": "ok"}), 200

    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])[0]
        messages_type = messages[MessageObjects.TYPE]
        sender_id = messages[MessageObjects.FROM]

        if messages_type == MessageTypes.INTERACTIVE:
            interactive_type = messages[MessageTypes.INTERACTIVE][MessageObjects.TYPE]
            if interactive_type == ReplyType.BUTTON_REPLY:
                button_reply = messages[MessageTypes.INTERACTIVE][ReplyType.BUTTON_REPLY]
                selected_option = button_reply[MessageObjects.TITLE]
                selected_option_id = button_reply[MessageObjects.ID]
                
                if selected_option_id == AppointmentConstants.ID:
                    if sender_id not in bot.user_states:
                        bot.initialize_user(sender_id)
                    reply_text = f"You have selected to book an appointment. Processing your request..."
                    send_text_message(sender_id, reply_text)
                    message = bot.get_next_message(sender_id)
                    send_message(message)

                else:
                    reply_text = f"You selected: {selected_option}"
                    send_text_message(sender_id, reply_text)

                return jsonify({"status": "ok"}), 200
        elif sender_id in bot.user_states:
            print(f"user is initiated booking process")
            response = messages["text"]["body"]
            message = bot.get_next_message(sender_id,response)
            send_message(message)
            return jsonify({"status": "ok"}), 200

        if is_valid_whatsapp_message(body):
            process_whatsapp_message(body)
            return jsonify({"status": "ok"}), 200
        else:
            # if the request is not a WhatsApp API event, return an error
            return (
                jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                404,
            )
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON")
        return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400

def send_text_message(recipient_id, text):
    """
    Send a text message to a specific recipient via the WhatsApp Business API.

    :param recipient_id: The recipient's phone number (including country code).
    :param text: The text message to be sent.
    """
    headers = {
        'Authorization': f'Bearer {current_app.config["ACCESS_TOKEN"]}',
        'Content-Type': 'application/json'
    }

    data = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        "type": "text",
        "text": {
            "body": text
        }
    })
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        log_http_response(response)
        return response

    logging.info(f"Message sent response: {response.json()}")

# Required webhook verification for WhatsApp
def verify():
    # Parse params from the webhook verification request
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
            # Respond with 200 OK and challenge token from the request
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    return handle_message()

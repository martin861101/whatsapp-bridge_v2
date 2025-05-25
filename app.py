from flask import Flask, request, jsonify, render_template
import redis
from config import Config
import re
import logging

app = Flask(__name__)
app.config.from_object(Config)

# Configure basic logging
logging.basicConfig(level=app.config['LOG_LEVEL'],
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    r = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        password=Config.REDIS_PASSWORD, # [cite: 3]
        decode_responses=True
    )
    r.ping()
    logger.info("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}")
    r = None # Set to None if connection fails

@app.route('/')
def index():
    # Serves the main page that might contain the widget, or the widget itself directly
    # For simplicity, let's assume widget.html is the main page.
    return render_template('widget.html') # [cite: 5]

@app.route('/send', methods=['POST'])
def handle_send_message(): # Renamed for clarity
    if not r:
        logger.error("Redis connection not available.")
        return jsonify({"success": False, "error": "Server error: Could not connect to message queue"}), 500
        
    try:
        data = request.json
        user_phone_widget = data.get('user_phone', '').strip() # Website user's phone number
        message_widget = data.get('message', '').strip()

        # Validate website user's phone number (sender)
        # Basic validation: starts with + and has at least 7 digits
        if not re.match(r'^\+[1-9]\d{6,14}$', user_phone_widget):
            return jsonify({"success": False, "error": "Invalid user phone number format. Must start with country code e.g. +123..."}), 400
        
        if not message_widget:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400

        # Construct the message to be sent to the business's WhatsApp
        # The recipient is the business's WhatsApp number from config
        recipient_business_whatsapp = Config.BUSINESS_WHATSAPP_NUMBER
        
        # Message format: Identify the sender (website user)
        # You might want to include more details if captured from the widget (e.g., name, email)
        formatted_message_to_business = f"New query from website visitor ({user_phone_widget}):\n\n{message_widget}"

        # Queue message for sending to the business
        payload = f"{recipient_business_whatsapp}||{formatted_message_to_business}"
        r.rpush(Config.REDIS_WHATSAPP_QUEUE, payload)
        logger.info(f"Queued message for {recipient_business_whatsapp} from {user_phone_widget}")
        
        return jsonify({
            "success": True,
            "message": "Message successfully queued for delivery to business."
        })
    
    except Exception as e:
        logger.error(f"Error in /send endpoint: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e) # [cite: 5]
        }), 500

if __name__ == '__main__':
    # Note: Flask-SocketIO is not used in this simplified concept for app.py
    # If you need real-time updates to the widget *from this server*, you'd re-add it.
    app.run(host='0.0.0.0', port=5000, debug=False) # Set debug=False for production
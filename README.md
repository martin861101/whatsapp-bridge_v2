# whatsapp-bridge_v2
WhatsApp bridge for communication from a web widget to WhatsApp (no API required) -- (Mail server required)
Widget for Initiation, Email-Powered WhatsApp Replies

This approach focuses on using your website widget for users to send their initial message. Your business then receives this on WhatsApp. To reply, your team sends an email to a special address, and the system converts that email into a WhatsApp message sent back to the user.
This means Selenium will only be used for sending WhatsApp messages (both the initial one from the website visitor and the replies from your business that are routed via email). We will not be attempting to scrape incoming messages using Selenium.
Here's the code for each relevant file. Remember to have your environment set up (Python, pip, Redis, and the necessary browser/WebDriver for Selenium).
1. config.py
This file will store your configurations. We'll add a configuration for your business's WhatsApp number, which will be the recipient of messages from the website widget.
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

class Config:
    """
    Configuration settings for the WhatsApp bridge application.
    Environment variables are used where appropriate for sensitive or
    deployment-specific settings.
    """
    # --- IMAP Configuration (for receiving emails from your team to send as WhatsApp replies) ---
    IMAP_SERVER = os.getenv("IMAP_SERVER", "IMAP_SERVER") # [cite: 2]
    IMAP_USER = os.getenv("IMAP_USER", YOUR_USER_NAME ") # [cite: 2]
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "YOUR_PASSWORD")  # Should be in .env in production [cite: 2]
    # Convention for email subject to identify recipient phone number for WhatsApp reply
    # Example: "WHATSAPPTO: +1234567890"
    IMAP_REPLY_SUBJECT_PREFIX = os.getenv("IMAP_REPLY_SUBJECT_PREFIX", "WHATSAPPTO:")

    # --- WhatsApp Configuration ---
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", 5))  # Messages per minute [cite: 2]
    CHROME_PROFILE_PATH = os.path.expanduser( # This might be used by Selenium if not using temp profiles
        os.getenv("CHROME_PROFILE_PATH", "~/.whatsapp_profiles/whatsapp_session")
    ) # [cite: 3]
    # Your Business's WhatsApp Number (where messages from the widget are sent)
    BUSINESS_WHATSAPP_NUMBER = os.getenv("BUSINESS_WHATSAPP_NUMBER", "+12345678901") # Replace with your actual business WhatsApp number

    # --- Redis Configuration ---
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost") # [cite: 3]
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379)) # [cite: 3]
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None) # [cite: 3]
    REDIS_WHATSAPP_QUEUE = "whatsapp_queue" # Name of the Redis queue

    # --- Flask Configuration ---
    SECRET_KEY = os.getenv("FLASK_SECRET", "your_insecure_development_secret_key") # [cite: 3]
    if SECRET_KEY == "your_insecure_development_secret_key":
        print("WARNING: Using default insecure FLASK_SECRET. Set FLASK_SECRET in production!") # [cite: 3, 4]

    # --- Logging Configuration ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # [cite: 4]

    # --- Selenium Configuration ---
    SELENIUM_HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'

Create a .env file in your project root for sensitive data (like passwords, actual phone numbers):

MAP_SERVER=your.imapserver.com
IMAP_USER=your-email@example.com
IMAP_PASSWORD=your-email-password
BUSINESS_WHATSAPP_NUMBER=+12345678901 # Your business WhatsApp number
FLASK_SECRET=a_very_strong_random_secret_key
# Optional:
# REDIS_HOST=localhost
# REDIS_PORT=6379
# CHROME_PROFILE_PATH="~/.config/google-chrome/whatsapp_profile"
# HEADLESS=true


2. templates/widget.html
This is the frontend chat widget. It will now include a field for the user's WhatsApp number.

<!DOCTYPE html>
<html>
<head>
    <title>WhatsApp Chat Widget</title>
    <style>
        /* Using styles from the provided document [cite: 11, 12, 13, 14, 15, 16, 17, 18] */
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        #whatsapp-widget-container { /* Added a container for centering the widget for demo */
            width: 350px;
            position: relative; /* Changed from fixed for demo purposes if not embedded in a larger site */
            /* For fixed position on a real site:
            position: fixed;
            bottom: 20px;
            right: 20px;
            */
            z-index: 1000;
        }
        #whatsapp-button {
            background: #25D366; color: white; border: none; border-radius: 50%;
            width: 60px; height: 60px; font-size: 24px; cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); transition: transform 0.3s;
            display: flex; align-items: center; justify-content: center;
        }
        #whatsapp-button:hover { transform: scale(1.1); }
        #whatsapp-chat {
            display: none; /* Initially hidden */
            width: 100%; /* Full width of container */
            background: white; border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            /* position: absolute; bottom: 70px; right: 0; */ /* Adjust if button is separate */
            flex-direction: column;
        }
        .chat-header {
            background: #075E54; color: white; padding: 12px;
            border-top-left-radius: 10px; border-top-right-radius: 10px;
            font-weight: bold; display: flex; justify-content: space-between; align-items: center;
        }
        #chat-messages {
            padding: 15px; max-height: 250px; overflow-y: auto; background: #f5f5f5;
            flex-grow: 1; display: flex; flex-direction: column;
        }
        .message-input-area { /* Renamed for clarity */
            padding: 10px; border-top: 1px solid #eee; display: flex; background: white;
            border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;
        }
        #user-phone {
            padding: 8px; border: 1px solid #ddd; border-radius: 20px; margin-bottom: 8px;
            outline: none; width: calc(100% - 20px);
        }
        #user-message {
            flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 20px; outline: none;
        }
        #send-button {
            background:#25D366; color:white; border:none; border-radius:50%;
            width:40px; height:40px; margin-left:5px; cursor:pointer;
            display: flex; align-items: center; justify-content: center;
        }
        .message {
            margin: 4px 0; padding: 8px 12px; border-radius: 18px; line-height: 1.4;
            word-wrap: break-word; max-width: 80%; clear: both;
        }
        .sent { background: #DCF8C6; color: #000; float: right; }
        .status { text-align: center; color: #888; font-size: 12px; margin: 4px 0; float: none; clear: both; }
        .error { background: #ffdddd; color: #d8000c; float: left; } /* [cite: 27] */
    </style>
</head>
<body>
    <div id="whatsapp-widget-container">
        <button id="whatsapp-button">💬</button>
        <div id="whatsapp-chat">
            <div class="chat-header">
                <span>Chat with Us</span>
                <span id="close-chat" style="cursor:pointer;">&times;</span>
            </div>
            <div id="chat-messages">
                <div class="message status">Please enter your WhatsApp number and message to start. We'll reply on WhatsApp.</div>
            </div>
            <div class="message-input-area" style="flex-direction: column;">
                <input type="tel" id="user-phone" placeholder="Your WhatsApp Number (e.g., +123...)" required>
                <div style="display: flex;">
                    <input type="text" id="user-message" placeholder="Type a message..." required>
                    <button id="send-button">➤</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const chatButton = document.getElementById('whatsapp-button');
            const chatWindow = document.getElementById('whatsapp-chat');
            const closeChatButton = document.getElementById('close-chat');
            const userPhoneInput = document.getElementById('user-phone');
            const userMessageInput = document.getElementById('user-message');
            const sendButton = document.getElementById('send-button');
            const chatMessages = document.getElementById('chat-messages');

            chatButton.addEventListener('click', function() {
                chatWindow.style.display = 'flex'; // Changed to flex
                chatButton.style.display = 'none';
                userPhoneInput.focus();
            });

            closeChatButton.addEventListener('click', function() {
                chatWindow.style.display = 'none';
                chatButton.style.display = 'flex'; // Changed to flex
            });

            async function handleSendMessage() {
                const phone = userPhoneInput.value.trim();
                const message = userMessageInput.value.trim();

                if (!phone) {
                    addMessageToUI('Please enter your WhatsApp phone number.', 'error');
                    userPhoneInput.focus();
                    return;
                }
                // Basic phone validation (starts with +, then digits)
                if (!/^\+[0-9]{7,}$/.test(phone)) {
                     addMessageToUI('Invalid phone number. Please use format like +1234567890.', 'error');
                     userPhoneInput.focus();
                     return;
                }
                if (!message) {
                    addMessageToUI('Message cannot be empty.', 'error');
                    userMessageInput.focus();
                    return;
                }

                addMessageToUI(message, 'sent');
                userMessageInput.value = ''; // Clear input [cite: 22]

                try {
                    const response = await fetch('/send', { // [cite: 22]
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_phone: phone, // Website user's WhatsApp number
                            message: message
                        })
                    });
                    const data = await response.json(); // [cite: 23]
                    if (data.success) {
                        addMessageToUI('Message sent! We will reply to your WhatsApp.', 'status'); // [cite: 24]
                    } else {
                        throw new Error(data.error || 'Failed to send message.'); // [cite: 23]
                    }
                } catch (error) {
                    addMessageToUI(`Error: ${error.message}`, 'error'); // [cite: 24]
                    // Optionally, re-add the original message to the input or allow resend
                    // For now, just show error.
                }
            }

            sendButton.addEventListener('click', handleSendMessage);
            userMessageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') handleSendMessage();
            });
             userPhoneInput.addEventListener('keypress', function(e) { // Allow enter from phone field too if message exists
                if (e.key === 'Enter' && userMessageInput.value.trim()) handleSendMessage();
            });

            function addMessageToUI(text, type) {
                const messageDiv = document.createElement('div');
                messageDiv.classList.add('message', type); // [cite: 25, 26]
                messageDiv.textContent = text;
                chatMessages.appendChild(messageDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight; // [cite: 28]
            }
        });
    </script>
</body>
</html>

3. app.py (Flask Server)
This handles incoming messages from the widget and queues them.
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

4. email_processor.py
This script processes emails sent by your business team (to the configured IMAP_USER email address) and queues them as WhatsApp messages to be sent to your website users.
import imaplib
import email
from email.header import decode_header
import time
import redis
from config import Config
import logging
import re # For parsing phone number from subject

# Configure logging
logging.basicConfig(
    level=Config.LOG_LEVEL, # Use LOG_LEVEL from Config
    format='%(asctime)s - %(levelname)s - %(message)s (email_processor)',
    handlers=[
        logging.FileHandler('email_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Redis connection
try:
    r = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        password=Config.REDIS_PASSWORD, # [cite: 3]
        decode_responses=True
    )
    r.ping()
    logger.info("Email Processor: Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Email Processor: Could not connect to Redis: {e}")
    r = None 

def extract_phone_from_subject(subject_str, prefix):
    """
    Extracts phone number from subject based on a prefix.
    Example: If subject is "WHATSAPPTO: +1234567890 Message for user" and prefix is "WHATSAPPTO:",
    it will attempt to extract "+1234567890".
    """
    if prefix.lower() in subject_str.lower():
        # Remove prefix (case-insensitive)
        phone_part = re.split(prefix, subject_str, flags=re.IGNORECASE)[-1]
        # Try to find a phone number pattern (e.g., + followed by digits)
        match = re.search(r'(\+\d+)', phone_part)
        if match:
            phone_number = match.group(1).strip()
            # Further validation (e.g. length) can be added here
            if re.match(r'^\+[1-9]\d{6,14}$', phone_number): # Basic validation
                return phone_number
    return None

def process_emails():
    if not r:
        logger.error("Email Processor: No Redis connection. Exiting.")
        return

    logger.info(f"Starting email processor for {Config.IMAP_USER}")
    
    while True:
        try:
            logger.info(f"Connecting to IMAP server {Config.IMAP_SERVER}...")
            mail = imaplib.IMAP4_SSL(Config.IMAP_SERVER, port=993) # [cite: 7] (assuming SSL, standard port)
            
            logger.info(f"Logging in as {Config.IMAP_USER}...")
            mail.login(Config.IMAP_USER, Config.IMAP_PASSWORD)
            logger.info("IMAP login successful.")
            
            mail.select("inbox") # [cite: 7]
            logger.info("INBOX selected. Waiting for new emails...")

            while True: # Keep checking for emails
                # Search for all unseen emails
                status, messages = mail.search(None, 'UNSEEN') # [cite: 7]
                if status != 'OK':
                    logger.error("IMAP search command failed.")
                    break # Break inner loop to reconnect

                if not messages[0]: # No unseen messages
                    time.sleep(30) # Wait before checking again
                    # Periodically send NOOP to keep connection alive
                    if mail.noop()[0] != 'OK':
                        logger.warning("IMAP NOOP failed. Connection may be stale.")
                        break # Break inner loop to reconnect
                    continue

                logger.info(f"Found {len(messages[0].split())} unseen email(s).")

                for num in messages[0].split():
                    try:
                        status, data = mail.fetch(num, '(RFC822)') # [cite: 7]
                        if status != 'OK':
                            logger.warning(f"Failed to fetch email UID {num.decode()}.")
                            continue
                        
                        msg = email.message_from_bytes(data[0][1]) # [cite: 8]
                        
                        subject_header = msg["Subject"]
                        subject = ""
                        if subject_header:
                            decoded_subject_parts = decode_header(subject_header) # [cite: 8]
                            for part, charset in decoded_subject_parts:
                                if isinstance(part, bytes):
                                    subject += part.decode(charset or 'utf-8', errors='ignore')
                                else:
                                    subject += part
                        logger.info(f"Processing email with Subject: {subject}")

                        # Extract phone number using the prefix from config
                        phone_to_reply = extract_phone_from_subject(subject, Config.IMAP_REPLY_SUBJECT_PREFIX)

                        if not phone_to_reply:
                            logger.warning(f"Could not extract valid recipient phone number from subject: '{subject}'. Marking as seen.")
                            mail.store(num, '+FLAGS', '\\Seen') # [cite: 8]
                            continue

                        # Get message body (prefer plain text)
                        body = ""
                        if msg.is_multipart(): # [cite: 8]
                            for part in msg.walk(): # [cite: 8]
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition: # [cite: 8]
                                    try:
                                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore') # [cite: 8]
                                        break
                                    except Exception as e:
                                        logger.error(f"Error decoding part for multipart: {e}")
                            if not body: # Fallback if no plain text found or error
                                for part in msg.walk():
                                     if "attachment" not in content_disposition and part.get_payload(decode=True):
                                        try:
                                            body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                                            if body.strip(): break # Take first non-empty part
                                        except: continue
                        else: # Not multipart
                            try:
                                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-config_enctf-8', errors='ignore') # [cite: 8]
                            except Exception as e:
                                logger.error(f"Error decoding body for non-multipart: {e}")
                        
                        body = body.strip()

                        if not body:
                            logger.warning(f"Email body is empty for subject: '{subject}'. Marking as seen.")
                            mail.store(num, '+FLAGS', '\\Seen')
                            continue
                        
                        # Queue for WhatsApp sending
                        payload = f"{phone_to_reply}||{body}"
                        r.rpush(Config.REDIS_WHATSAPP_QUEUE, payload)
                        logger.info(f"Queued WhatsApp reply to {phone_to_reply} from email (Subject: {subject})")
                        
                        # Mark email as read (Seen)
                        mail.store(num, '+FLAGS', '\\Seen') # [cite: 8]
                        logger.info(f"Marked email UID {num.decode()} as seen.")

                    except Exception as e:
                        logger.error(f"Error processing email UID {num.decode() if isinstance(num, bytes) else num}: {e}", exc_info=True)
                        # Decide if you want to mark as seen on error or retry later
                        # mail.store(num, '+FLAGS', '\\Seen') 
                        continue # Process next email
                
                # Check for shutdown flag if implemented, or just loop
                time.sleep(10) # Wait before scanning for new messages again after processing a batch

        except imaplib.IMAP4.abort as e: # Specific error for IMAP abort like connection closed by server
            logger.error(f"IMAP connection aborted: {e}. Reconnecting in 60s...")
            time.sleep(60)
        except imaplib.IMAP4.error as e: # Other IMAP errors
            logger.error(f"IMAP error: {e}. Reconnecting in 60s...")
            time.sleep(60)
        except Exception as e:
            logger.error(f"General error in email processing loop: {e}", exc_info=True)
            logger.info("Attempting to logout and reconnect in 60 seconds...")
            try:
                if 'mail' in locals() and mail.state != 'LOGOUT':
                    mail.logout()
            except:
                pass
            time.sleep(60) # Wait before retrying connection
        finally:
            try:
                if 'mail' in locals() and mail.state != 'LOGOUT':
                    logger.info("Closing IMAP connection.")
                    mail.close()
                    mail.logout()
            except Exception as e_logout:
                logger.error(f"Error during IMAP logout/close: {e_logout}")

if __name__ == '__main__':
    if r is None:
        logger.error("Email Processor: Cannot start without Redis connection.")
    else:
        process_emails()

5. queue_processor.py
This file takes messages from the Redis queue and uses WhatsAppSender to send them. The version from your document, with the logging and graceful shutdown improvements discussed in the previous debugging session, should work well here. I'll provide the version that includes the current_whatsapp_sender management for robustness.


import time
import redis
from whatsapp_sender import WhatsAppSender # This should be your latest working/debugged version
from config import Config
import logging
import signal

# Configure logging using LOG_LEVEL from Config
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s (queue_processor)'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown and current sender instance
shutdown_flag = False
current_whatsapp_sender = None 

def signal_handler(sig, frame):
    global shutdown_flag
    logger.info(f"Shutdown signal {sig} received. Initiating graceful shutdown.")
    shutdown_flag = True

class RedisManager:
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                password=Config.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=10, # Timeout for socket operations
                socket_connect_timeout=5 # Timeout for establishing connection
            )
            self.connection.ping()
            logger.info("RedisManager: Successfully connected to Redis.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"RedisManager: Could not connect to Redis: {e}")
            self.connection = None
    
    def get_connection(self):
        if not self.is_connected():
            self.connect()
        return self.connection

    def is_connected(self):
        if not self.connection:
            return False
        try:
            self.connection.ping()
            return True
        except redis.exceptions.ConnectionError:
            logger.warning("RedisManager: Ping failed. Connection lost.")
            self.connection = None # Ensure connection is None if ping fails
            return False

def initialize_whatsapp_instance(max_retries=3, retry_delay=10):
    global current_whatsapp_sender
    
    if current_whatsapp_sender and current_whatsapp_sender.driver:
        logger.info("Closing existing WhatsApp sender before (re)initializing.")
        current_whatsapp_sender.close()
        current_whatsapp_sender = None

    for attempt in range(1, max_retries + 1):
        if shutdown_flag:
            logger.info("Shutdown initiated, aborting WhatsApp initialization.")
            return None

        logger.info(f"Initializing WhatsApp (Attempt {attempt}/{max_retries})")
        sender_instance = WhatsAppSender() 
        if sender_instance.initialize(): # initialize now returns True/False
            logger.info("WhatsApp initialized successfully.")
            current_whatsapp_sender = sender_instance
            return sender_instance
        else:
            logger.warning(f"WhatsApp initialization failed on attempt {attempt}.")
            # The sender_instance.initialize() or sender_instance.close() should handle cleanup of its own resources
            # sender_instance.close() # Called within initialize on failure, or if it returns False, we call it here.
            # Ensure temp dirs are cleaned up if initialize fails.
            # The WhatsAppSender's initialize method should ideally clean up its temp dir if it fails.
            # If not, ensure sender_instance.close() is called.
            if hasattr(sender_instance, 'close') and callable(getattr(sender_instance, 'close')):
                sender_instance.close()

            if attempt < max_retries:
                logger.info(f"Retrying WhatsApp initialization in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Max WhatsApp initialization attempts reached. Initialization failed.")
                
    current_whatsapp_sender = None 
    return None

def process_queue(redis_conn):
    global current_whatsapp_sender
    global shutdown_flag
    
    # Ensure WhatsApp sender is ready
    if not current_whatsapp_sender or not current_whatsapp_sender.driver:
        logger.info("WhatsApp sender not initialized or driver lost. Attempting to initialize.")
        if not initialize_whatsapp_instance():
            logger.error("Failed to initialize WhatsApp for queue processing. Will retry later.")
            return False # Indicate failure to process this cycle

    sender_to_use = current_whatsapp_sender

    try:
        # Blocking pop with timeout to allow checking shutdown_flag periodically
        item = redis_conn.blpop(Config.REDIS_WHATSAPP_QUEUE, timeout=5)
        
        if shutdown_flag: 
            logger.info("Shutdown signal received during queue wait.")
            return True # Indicate clean exit from this call
        
        if not item:
            return True # Queue empty, no error, continue main loop

        _, payload = item
        try:
            phone, message = payload.split("||", 1)
            phone = phone.strip()
        except ValueError:
            logger.error(f"Invalid queue item format: {payload}. Discarding.")
            return True # Continue to next item
        
        logger.info(f"Processing message from queue for {phone}")
        
        if sender_to_use.send_message(phone, message):
            logger.info(f"Message sent to {phone} successfully.")
        else:
            logger.warning(f"Failed to send message to {phone}. Requeuing.")
            redis_conn.rpush(Config.REDIS_WHATSAPP_QUEUE, payload) # Requeue on failure
            
            # Trigger re-initialization of WhatsApp sender as it might be in a bad state
            logger.info("Attempting to re-initialize WhatsApp sender due to send failure.")
            if not initialize_whatsapp_instance(max_retries=1): # Attempt a quick re-init
                logger.error("Reinitialization failed after send error. Message remains queued. Pausing processing.")
                return False # Critical failure with WhatsApp sender
            # current_whatsapp_sender would be updated by initialize_whatsapp_instance

    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection lost during queue processing: {e}")
        return False # Signal to main loop to re-check Redis connection
        
    except Exception as e:
        logger.error(f"Unexpected error in process_queue: {e}", exc_info=True)
        # Depending on error, might requeue or discard. For now, log and continue.
        # if 'payload' in locals() and payload: # if payload was retrieved
        #    redis_conn.rpush(Config.REDIS_WHATSAPP_QUEUE, payload) # Example: requeue on unknown error
        time.sleep(5) # Brief pause
        return True # Continue loop

    return True # Successfully processed an item or queue was empty

def main():
    global current_whatsapp_sender
    global shutdown_flag

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting WhatsApp Queue Processor")
    
    redis_manager = RedisManager()
    
    while not shutdown_flag:
        if not redis_manager.is_connected():
            logger.error("Queue Processor: Cannot connect to Redis. Retrying in 10s...")
            time.sleep(10)
            if shutdown_flag: break
            continue
        
        redis_conn = redis_manager.get_connection()

        # Ensure WhatsApp is initialized (or re-initialized if needed)
        if not current_whatsapp_sender or not current_whatsapp_sender.driver:
            logger.info("Main loop: WhatsApp sender check failed. Initializing...")
            initialize_whatsapp_instance() 
            if not current_whatsapp_sender and not shutdown_flag: 
                logger.error("Main loop: Failed to initialize WhatsApp. Waiting before retrying...")
                time.sleep(30) 
                if shutdown_flag: break
                continue 
        
        # Process one item from the queue (or wait for one)
        success = process_queue(redis_conn) 
        
        if not success and not shutdown_flag: # Indicates a critical error (Redis/WhatsApp init)
            logger.info("Processing cycle indicated critical failure. Waiting 30 seconds...")
            time.sleep(30) 
        # If success is True, it means either an item was processed, queue was empty, or shutdown started.
        # No need for extensive sleep if queue is just empty, blpop handles timeout.
            
    logger.info("Shutting down Queue Processor. Closing WhatsApp sender if active.")
    if current_whatsapp_sender:
        current_whatsapp_sender.close()
        
    logger.info("Queue Processor service stopped gracefully.")

if __name__ == '__main__':
    main()

6. whatsapp_sender.py
Use the version from the previous step which includes verbose ChromeDriver logging and explicit use of chromedriver-autoinstaller. This was the last version we worked on for debugging Selenium initialization. I'll reproduce it here for completeness, assuming it's the most up-to-date for your debugging.

import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service 
import chromedriver_autoinstaller 
from config import Config
import time
import tempfile
import shutil
import logging
import urllib.parse

logger = logging.getLogger(__name__) # Will inherit config from queue_processor or main script

class WhatsAppSender:
    def __init__(self):
        self.driver = None
        self.message_count = 0
        self.window_start = time.time()
        self.user_data_dir = tempfile.mkdtemp() # Each instance gets its own temp dir
        logger.info(f"WhatsAppSender instance created. User data dir: {self.user_data_dir}")

    def initialize(self):
        logger.info(f"Initializing WebDriver with user_data_dir: {self.user_data_dir}")
        options = ChromeOptions()
        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        
        if Config.SELENIUM_HEADLESS: # Use from Config
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox") 
            options.add_argument("--disable-dev-shm-usage") 
            options.add_argument("--window-size=1920,1080")
        
        try:
            try:
                chromedriver_path = chromedriver_autoinstaller.install()
                logger.info(f"Using chromedriver at: {chromedriver_path}")
            except Exception as e:
                logger.error(f"Could not install/find chromedriver using autoinstaller: {e}. Selenium will try PATH.")
                chromedriver_path = "chromedriver" 

            log_file_path = os.path.join(os.getcwd(), "chromedriver.log") 
            logger.info(f"ChromeDriver verbose log will be at: {log_file_path}")
            
            # Check Selenium version for log_output vs log_path
            # For Selenium 4.6+ log_output is the way, older is log_path
            # Assuming a relatively modern Selenium version.
            # If this errors, try 'log_path=log_file_path'
            service = Service(executable_path=chromedriver_path,
                              service_args=['--verbose'],
                              log_output=log_file_path) 

            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get("https://web.whatsapp.com")
            
            logger.info("Waiting for WhatsApp Web to load (QR scan if needed - 120s timeout)...")
            # Wait for a known element that indicates WhatsApp Web is ready after QR scan
            # This XPath looks for the "Chats" title, or alternatively, the search input field.
            WebDriverWait(self.driver, 120).until(
                 EC.any_of(
                    EC.presence_of_element_located((By.XPATH, '//div[@title="Chats"]')),
                    EC.presence_of_element_located((By.XPATH, '//div[@role="textbox"][@aria-label="Search input textbox"]'))
                )
            )
            logger.info("WhatsApp Web loaded successfully (found Chats title or Search input).")
            return True
        except TimeoutException:
            logger.error("TimeoutException: WhatsApp Web (QR scan page or main interface) did not load in time.")
            self.close() 
            return False
        except WebDriverException as e: 
            logger.error(f"WebDriverException during initialization: {e}")
            self.close() 
            return False
        except Exception as e: 
            logger.error(f"Unexpected error during WebDriver initialization: {e}", exc_info=True)
            self.close()
            return False

    def send_message(self, phone, message):
        if not self.driver:
            logger.error("Driver not initialized. Cannot send message.")
            return False
        try:
            # Rate limiting from original document [cite: 3]
            current_time = time.time()
            if self.message_count >= Config.RATE_LIMIT:
                elapsed = current_time - self.window_start
                if elapsed < 60:
                    sleep_duration = 60 - elapsed
                    logger.info(f"Rate limit hit ({Config.RATE_LIMIT} messages/min). Sleeping for {sleep_duration:.2f} seconds.")
                    time.sleep(sleep_duration)
                self.message_count = 0
                self.window_start = time.time() # Reset window after waiting or after 60s
            
            encoded_message = urllib.parse.quote(message)
            url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0" # app_absent=0 can help
            logger.info(f"Navigating to chat URL for {phone}")
            self.driver.get(url)
            
            # Wait for the main message input box to ensure page is ready for send button
            # Using a more robust XPath for the message input box.
            # This XPath is more general, looking for a div with role="textbox" that would be the main composer.
            message_box_xpath = '//div[@role="textbox"][@contenteditable="true"][@data-tab="10"]' # Common XPath for WA Web message box
            # Alternative simpler one: '//div[@title="Type a message"]' (but can change)

            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, message_box_xpath))
                )
                logger.info("Message input box found.")
            except TimeoutException:
                logger.error(f"Timeout: Could not find message input box for {phone}. Number might be invalid or chat not opening.")
                # Check for "Phone number shared via url is invalid."
                try:
                    invalid_phone_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Phone number shared via url is invalid')]")
                    if invalid_phone_element:
                        logger.warning(f"WhatsApp reported invalid phone number for {phone}.")
                        return False # Don't try to click send
                except NoSuchElementException:
                    pass # Error is something else
                return False

            # Wait for send button (common XPaths) [cite: 6]
            send_button_xpaths = [
                '//button[@aria-label="Send"]',
                '//span[@data-icon="send"]',
                '//button[@data-testid="compose-btn-send"]'
            ]
            send_btn = None
            for i, xpath in enumerate(send_button_xpaths):
                try:
                    send_btn = WebDriverWait(self.driver, 10 if i < len(send_button_xpaths) -1 else 20).until( # Shorter timeout for initial tries
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    logger.info(f"Send button found with XPath: {xpath}")
                    break 
                except TimeoutException:
                    logger.debug(f"Send button not found with XPath: {xpath}")
            
            if not send_btn:
                logger.error(f"TimeoutException: Send button not found for {phone} after trying multiple XPaths.")
                # self.driver.save_screenshot(f"send_button_not_found_{phone}.png") # For debugging
                return False

            send_btn.click()
            logger.info(f"Clicked send button for {phone}.")
            
            self.message_count += 1
            time.sleep(2) # Brief pause to allow message to process/send
            return True
            
        except TimeoutException as e:
            logger.error(f"TimeoutException during send_message to {phone}: {e}")
            # self.driver.save_screenshot(f"timeout_send_message_{phone}.png")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during send_message to {phone}: {e}", exc_info=True)
            # self.driver.save_screenshot(f"error_send_message_{phone}.png")
            return False

    def close(self):
        logger.info(f"Closing WhatsAppSender. UserDataDir: {self.user_data_dir}")
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver quit successfully.")
            except Exception as e:
                logger.error(f"Error quitting driver: {e}")
            self.driver = None
        
        if self.user_data_dir:
            try:
                if os.path.exists(self.user_data_dir):
                     shutil.rmtree(self.user_data_dir)
                     logger.info(f"User data directory {self.user_data_dir} removed successfully.")
                else: # Should not happen if mkdtemp was successful
                    logger.warning(f"User data directory {self.user_data_dir} not found for removal.")
            except Exception as e:
                logger.error(f"Error removing user_data_dir {self.user_data_dir}: {e}")
            self.user_data_dir = None

7. requirements.txt
Based on the code and original document.
flask # [cite: 30]
redis # [cite: 30]
python-dotenv # [cite: 30]
selenium # [cite: 30]
# imapclient is listed in the doc, but standard imaplib is used here. [cite: 30]
# If you specifically want imapclient, add it and adjust email_processor.py
chromedriver-autoinstaller # [cite: 30]
# Add any other specific versions if needed, e.g., Flask==2.3.2

To Run This System:
1.	Setup Environment:
o	Install Python 3.
o	Create a virtual environment: python3 -m venv venv and source venv/bin/activate.
o	Install requirements: pip install -r requirements.txt.
o	Install and run Redis server (e.g., sudo systemctl start redis-server or via Docker).
o	Ensure you have Google Chrome installed (for Selenium). chromedriver-autoinstaller should handle the driver.
2.	Configure:
o	Create and populate the .env file with your actual credentials and phone numbers as described for config.py.
o	Specifically, set BUSINESS_WHATSAPP_NUMBER in .env to your business's WhatsApp number that will receive initial messages.
o	Set up the email account (IMAP_USER, IMAP_PASSWORD, IMAP_SERVER in .env) that email_processor.py will monitor.
o	Define IMAP_REPLY_SUBJECT_PREFIX in .env (default is WHATSAPPTO:). Your team will use this prefix in the subject line of emails they send to the monitored account when they want to reply to a website user via WhatsApp. For example, Subject: WHATSAPPTO: +19876543210 This is our reply.
3.	Run the Services (each in a separate terminal):
o	python3 app.py (Flask web server)
o	python3 email_processor.py (IMAP Email Handler)
o	python3 queue_processor.py (Redis Queue Worker & Selenium Interaction)
4.	First Run of queue_processor.py:
o	When queue_processor.py starts for the first time (or after a long time), whatsapp_sender.py will launch Chrome.
o	It will navigate to web.whatsapp.com. You will need to scan the QR code using the WhatsApp application on a phone that is linked to your BUSINESS_WHATSAPP_NUMBER.
o	Keep an eye on the terminal running queue_processor.py for logs, especially during this initialization. The chromedriver.log file will also contain verbose logs.
How the Business Team Replies:
1.	A website visitor sends a message via the widget. It arrives on your BUSINESS_WHATSAPP_NUMBER.
2.	Your team sees this message on their WhatsApp.
3.	To reply via WhatsApp through the system: 
o	They compose a new email.
o	To: The email address monitored by email_processor.py (e.g., martin@hookitupservices.com).
o	Subject: WHATSAPPTO: +[WebsiteUser_PhoneNumber] (e.g., WHATSAPPTO: +11223344556)
o	Body: The reply message.
o	Send the email.
4.	email_processor.py will pick this up, and the reply will be sent as a WhatsApp message to the WebsiteUser_PhoneNumber.
This setup provides a functional bridge based on your simplified "notification and email-powered reply" concept, focusing on robustness by avoiding Selenium-based message scraping. Remember to test thoroughly, especially the Selenium parts and the email parsing.
Sources 


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
    IMAP_SERVER = os.getenv("IMAP_SERVER", "mail.hookitupservices.com") # [cite: 2]
    IMAP_USER = os.getenv("IMAP_USER", "martin@hookitupservices.com") # [cite: 2]
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "FlamingoBB22@22")  # Should be in .env in production [cite: 2]
    # Convention for email subject to identify recipient phone number for WhatsApp reply
    # Example: "WHATSAPPTO: +1234567890"
    IMAP_REPLY_SUBJECT_PREFIX = os.getenv("IMAP_REPLY_SUBJECT_PREFIX", "WHATSAPPTO:")

    # --- WhatsApp Configuration ---
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", 5))  # Messages per minute [cite: 2]
    CHROME_PROFILE_PATH = os.path.expanduser( # This might be used by Selenium if not using temp profiles
        os.getenv("CHROME_PROFILE_PATH", "~/.whatsapp_profiles/whatsapp_session")
    ) # [cite: 3]
    # Your Business's WhatsApp Number (where messages from the widget are sent)
    BUSINESS_WHATSAPP_NUMBER = os.getenv("BUSINESS_WHATSAPP_NUMBER", "+27829274009") # Replace with your actual business WhatsApp number

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

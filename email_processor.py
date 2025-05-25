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
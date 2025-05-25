import time
import redis
from whatsapp_sender import WhatsAppSender
from config import Config
import logging
import signal

# Configure logging
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
                socket_timeout=10, 
                socket_connect_timeout=5 
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
            self.connection = None
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
        if sender_instance.initialize():
            logger.info("WhatsApp initialized successfully.")
            current_whatsapp_sender = sender_instance
            return sender_instance
        else:
            logger.warning(f"WhatsApp initialization failed on attempt {attempt}.")
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
            return False 

    sender_to_use = current_whatsapp_sender

    try:
        # Blocking pop with timeout to allow checking shutdown_flag periodically
        item = redis_conn.blpop(Config.REDIS_WHATSAPP_QUEUE, timeout=5)
        
        if shutdown_flag: 
            logger.info("Shutdown signal received during queue wait.")
            return True 
        
        if not item:
            return True # Queue empty, no error, continue main loop

        _, payload = item
        try:
            phone, message = payload.split("||", 1)
            phone = phone.strip()
        except ValueError:
            logger.error(f"Invalid queue item format: {payload}. Discarding.")
            return True 
        
        logger.info(f"Processing message from queue for {phone}")
        
        if sender_to_use.send_message(phone, message):
            logger.info(f"Message sent to {phone} successfully.")
        else:
            logger.warning(f"Failed to send message to {phone}. Requeuing.")
            redis_conn.rpush(Config.REDIS_WHATSAPP_QUEUE, payload)
            
            logger.info("Attempting to re-initialize WhatsApp sender due to send failure.")
            if not initialize_whatsapp_instance(max_retries=1):
                logger.error("Reinitialization failed after send error. Message remains queued. Pausing processing.")
                return False 

    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection lost during queue processing: {e}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error in process_queue: {e}", exc_info=True)
        time.sleep(5) 
        return True 

    return True

def main():
    global current_whatsapp_sender
    global shutdown_flag

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting WhatsApp Queue Processor")
    
    redis_manager = RedisManager()
    
    # --- ADDITION START ---
    # Clear the queue on startup for a clean slate during development/debugging
    # IMPORTANT: For production, you might want to remove or make this conditional
    # to avoid losing messages if the worker restarts unexpectedly.
    if redis_manager.is_connected():
        queue_name = Config.REDIS_WHATSAPP_QUEUE
        deleted_count = redis_manager.get_connection().delete(queue_name)
        logger.info(f"Cleared {deleted_count} old messages from Redis queue '{queue_name}' on startup.")
    else:
        logger.warning("Redis not connected on startup, could not clear queue.")
    # --- ADDITION END ---

    while not shutdown_flag:
        if not redis_manager.is_connected():
            logger.error("Queue Processor: Cannot connect to Redis. Retrying in 10s...")
            time.sleep(10)
            if shutdown_flag: break
            continue
        
        redis_conn = redis_manager.get_connection()

        if not current_whatsapp_sender or not current_whatsapp_sender.driver:
            logger.info("Main loop: WhatsApp sender check failed. Initializing...")
            initialize_whatsapp_instance() 
            if not current_whatsapp_sender and not shutdown_flag: 
                logger.error("Main loop: Failed to initialize WhatsApp. Waiting before retrying...")
                time.sleep(30) 
                if shutdown_flag: break
                continue 
        
        success = process_queue(redis_conn) 
        
        if not success and not shutdown_flag: 
            logger.info("Processing cycle indicated critical failure. Waiting 30 seconds...")
            time.sleep(30) 
            
    logger.info("Shutting down Queue Processor. Closing WhatsApp sender if active.")
    if current_whatsapp_sender:
        current_whatsapp_sender.close()
        
    logger.info("Queue Processor service stopped gracefully.")

if __name__ == '__main__':
    main()


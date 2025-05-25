import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
# chromedriver_autoinstaller is not actively used in this version, but keep if you might revert
# import chromedriver_autoinstaller 
from config import Config
import time
# tempfile and shutil are no longer needed if using a persistent profile for user_data_dir in this way
# import tempfile 
# import shutil   
import logging
import urllib.parse

logger = logging.getLogger(__name__) # Will inherit config from the script that runs this (e.g., queue_processor.py)

class WhatsAppSender:
    def __init__(self):
        self.driver = None
        self.message_count = 0
        self.window_start = time.time()
        # Use the persistent profile path from Config
        self.user_data_dir = Config.CHROME_PROFILE_PATH
        # Create the directory if it doesn't exist
        os.makedirs(self.user_data_dir, exist_ok=True)
        logger.info(f"WhatsAppSender instance created. User data dir (persistent): {self.user_data_dir}")

    def initialize(self):
        logger.info(f"Initializing WebDriver with user_data_dir: {self.user_data_dir}")
        options = ChromeOptions()
        # Critical: Add the user data directory argument
        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        
        # --- IMPORTANT: Add common flags for server environments unconditionally ---
        # These flags are often necessary when running as root or in minimal server setups.
        options.add_argument("--no-sandbox") # CRITICAL for running as root or in containers
        options.add_argument("--disable-dev-shm-usage") # Important for /dev/shm (shared memory) issues
        options.add_argument("--disable-gpu") # Good practice for server environments, even with a display

        # --- Configure HEADLESS or NON-HEADLESS based on Config ---
        if Config.SELENIUM_HEADLESS:
            logger.info("Configuring Chrome for HEADLESS mode (no visible GUI).")
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080") # Set a consistent window size for headless
        else:
            logger.info("Configuring Chrome for NON-HEADLESS (visible GUI) mode.")
            # No specific additional options needed here, as the common ones are added above.
            # If you want to force a specific window size for GUI mode, you can add it here:
            # options.add_argument("--window-size=1920,1080") 
        
        try:
            # Since you've confirmed matching Chrome and ChromeDriver versions 
            # are available and chromedriver is in your system PATH:
            chromedriver_executable_path = "chromedriver" 
            logger.info(f"Attempting to use ChromeDriver from system PATH by specifying: '{chromedriver_executable_path}'")

            log_file_path = os.path.join(os.getcwd(), "chromedriver.log")
            logger.info(f"ChromeDriver verbose log will be at: {log_file_path}")
            
            # Initialize the Service with the name "chromedriver"
            # Selenium will search for "chromedriver" in the directories listed in your system's PATH.
            service = Service(executable_path=chromedriver_executable_path,
                              service_args=['--verbose'],
                              log_output=log_file_path) # For Selenium 4.6+ (recommended)
                                                        # For older versions, you might use log_path=log_file_path

            self.driver = webdriver.Chrome(service=service, options=options)
            
            logger.info("Navigating to https://web.whatsapp.com")
            self.driver.get("https://web.whatsapp.com")
            
            # Increased timeout for initial login/QR scan.
            # If already logged in, this should pass quickly.
            login_timeout = 300 # 5 minutes for QR scan
            logger.info(f"Waiting for WhatsApp Web to load (QR scan if needed, or to load existing session - {login_timeout}s timeout)...")
            
            # Check if already logged in by looking for a key element of the main chat interface
            try:
                WebDriverWait(self.driver, 20).until( # Shorter timeout to check if already logged in
                    EC.any_of( # Wait for either of these elements to confirm page load
                        EC.presence_of_element_located((By.XPATH, '//div[@title="Chats"]')),
                        EC.presence_of_element_located((By.XPATH, '//div[@role="textbox"][@aria-label="Search input textbox"]'))
                    )
                )
                logger.info("WhatsApp Web is already logged in and loaded main interface.")
                return True
            except TimeoutException:
                logger.info("Main interface not immediately available. Expecting QR code page or longer load.")
                # Now wait longer for either the QR code (if needed) or the main interface to eventually load
                WebDriverWait(self.driver, login_timeout).until(
                     EC.any_of(
                        EC.presence_of_element_located((By.XPATH, '//div[@title="Chats"]')), # Main interface
                        EC.presence_of_element_located((By.XPATH, '//div[@role="textbox"][@aria-label="Search input textbox"]')), # Main interface
                        EC.presence_of_element_located((By.XPATH, '//canvas[@aria-label="Scan me!"]')), # QR Code
                        EC.presence_of_element_located((By.XPATH, '//div[@data-testid="qrcode"]')) # Alternative QR code element
                    )
                )
                # Check again if we landed on the main interface after the longer wait
                try:
                    WebDriverWait(self.driver, 5).until( # Give a short time to verify if it became main interface
                         EC.any_of(
                            EC.presence_of_element_located((By.XPATH, '//div[@title="Chats"]')),
                            EC.presence_of_element_located((By.XPATH, '//div[@role="textbox"][@aria-label="Search input textbox"]'))
                        )
                    )
                    logger.info("WhatsApp Web loaded successfully after longer wait (found Chats title or Search input).")
                except TimeoutException:
                    logger.info("Landed on QR code page or an intermediate state. User interaction (scan) is required if not headless.")
                    # If headless and stuck here, it means it needs QR scan but can't get it.
                    if Config.SELENIUM_HEADLESS:
                        logger.error("HEADLESS MODE: WhatsApp requires QR scan. Please run once with HEADLESS=false to scan the QR code using the persistent profile.")
                        self.close() # Clean up the newly created temp dir
                        return False
                return True # Assume it's either logged in or showing QR for non-headless

        # --- Error Handling for WebDriver Initialization ---
        except TypeError as te: 
            logger.error(f"TypeError during Service/WebDriver initialization (path issue?): {te}", exc_info=True)
            self.close()
            return False
        except TimeoutException: # This outer timeout is for the WebDriverWait calls above (if they time out before an expected element is found)
            logger.error(f"TimeoutException: WhatsApp Web (QR scan or main interface) did not load in {login_timeout}s.")
            self.close() 
            return False
        except WebDriverException as e: 
            logger.error(f"WebDriverException during initialization or navigation: {e}")
            if hasattr(e, 'msg') and e.msg: # msg attribute often contains more details from chromedriver
                logger.error(f"WebDriverException details: {e.msg}")
            self.close() 
            return False
        except Exception as e: # Catch any other unexpected errors during the process
            logger.error(f"Unexpected error during WebDriver initialization: {e}", exc_info=True)
            self.close()
            return False

    def send_message(self, phone, message):
        if not self.driver:
            logger.error("Driver not initialized. Cannot send message.")
            return False
        try:
            # Rate limiting
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
            # &app_absent=0 can sometimes help ensure it opens directly in WA Web
            url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0" 
            logger.info(f"Navigating to chat URL for {phone}")
            self.driver.get(url)
            
            # Wait for the main message input box to ensure page is ready for send button
            # This XPath is more general, looking for a div with role="textbox" that would be the main composer.
            message_box_xpath = '//div[@role="textbox"][@contenteditable="true"][@data-tab="10"]' 

            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, message_box_xpath))
                )
                logger.info("Message input box found.")
            except TimeoutException:
                logger.error(f"Timeout: Could not find message input box for {phone}. Number might be invalid or chat not opening.")
                try: # Check for specific WhatsApp error message for invalid numbers
                    invalid_phone_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Phone number shared via url is invalid')]")
                    if invalid_phone_element:
                        logger.warning(f"WhatsApp reported invalid phone number for {phone}.")
                        return False 
                except NoSuchElementException:
                    pass # The error was not the "invalid phone" message, proceed with general TimeoutException handling
                return False

            # Wait for send button (common XPaths)
            send_button_xpaths = [
                '//button[@aria-label="Send"]',
                '//span[@data-icon="send"]',
                '//button[@data-testid="compose-btn-send"]'
            ]
            send_btn = None
            for i, xpath in enumerate(send_button_xpaths):
                try:
                    # Adjust timeout: shorter for initial attempts, longer for the last one if still not found
                    timeout = 10 if i < len(send_button_xpaths) - 1 else 20 
                    send_btn = WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    logger.info(f"Send button found with XPath: {xpath}")
                    break # Exit loop once button is found
                except TimeoutException:
                    logger.debug(f"Send button not found with XPath: {xpath}. Trying next...")
            
            if not send_btn: # If button was not found after all attempts
                logger.error(f"TimeoutException: Send button not found for {phone} after trying multiple XPaths.")
                return False

            send_btn.click()
            logger.info(f"Clicked send button for {phone}.")
            
            self.message_count += 1
            time.sleep(2) # Brief pause to allow message to process/send
            return True
            
        except TimeoutException as e:
            logger.error(f"TimeoutException during send_message to {phone}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during send_message to {phone}: {e}", exc_info=True)
            return False

    def close(self):
        logger.info(f"Closing WhatsAppSender. Driver: {'Exists' if self.driver else 'None'}")
        # DO NOT delete the user_data_dir as it's configured to be persistent (Config.CHROME_PROFILE_PATH)
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver quit successfully.")
            except Exception as e:
                logger.error(f"Error quitting driver: {e}")
            self.driver = None
        
        # Removed the shutil.rmtree(self.user_data_dir) line because the profile is persistent.
        # logger.info(f"Persistent user data directory at {self.user_data_dir} will NOT be removed upon close.")


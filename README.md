# WhatsApp Bridge

This project bridges communications to WhatsApp, allowing messages to be sent via a web interface or processed from emails and then relayed through WhatsApp using Selenium to control a web browser.

## Project Structure

```
/whatsapp-bridge
│
├── /templates
│   └── widget.html       # Frontend chat widget
├── config.py             # Configuration
├── app.py                # Flask server for web interface
├── email_processor.py    # IMAP email handler
├── queue_processor.py    # Redis queue worker
├── whatsapp_sender.py    # Selenium controller for WhatsApp Web
└── requirements.txt      # Python dependencies
```

## Features

*   **Web Interface**: Send WhatsApp messages directly through a simple web form.
*   **Email-to-WhatsApp**: Monitors an IMAP email account, parses emails, and sends them as WhatsApp messages.
*   **Queue System**: Uses Redis to manage outgoing messages, ensuring reliability.
*   **Rate Limiting**: Basic rate limiting in the WhatsApp sender to avoid being blocked.
*   **Headless Browser Support**: Can run Chrome in headless mode for server environments.

## Setup and Deployment

### Prerequisites

*   Python 3.x
*   Redis Server
*   Google Chrome browser (for Selenium)
*   `chromedriver` compatible with your Chrome version (can be auto-installed by `chromedriver-autoinstaller`)

### Installation

1.  **Clone the repository (or set up the files as provided).**
2.  **Create a Python virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure `config.py`:**
    *   Update `IMAP_SERVER`, `IMAP_USER`, `IMAP_PASSWORD` with your email credentials.
    *   Adjust `CHROME_PROFILE_PATH` if needed (default is `/tmp/whatsapp_session`). Ensure this path is writable.
    *   Set `REDIS_HOST` and `FLASK_SECRET` environment variables or update them directly in `config.py`. Create a `.env` file in the `whatsapp-bridge` directory for these:
        ```env
        REDIS_HOST=localhost
        FLASK_SECRET=your_very_secret_flask_key
        # Set to 'false' if you need to scan QR code initially
        HEADLESS=true 
        ```

### Running the Services

1.  **Start Redis Server:**
    Ensure your Redis server is running.
    ```bash
    sudo systemctl start redis-server  # Example for systemd
    # Or, if running locally/manually: redis-server
    ```

2.  **Initialize WhatsApp Session (First Time):**
    *   Temporarily set `HEADLESS=false` in your `.env` file or environment.
    *   Run the `queue_processor.py` once: `python3 queue_processor.py`
    *   This will open WhatsApp Web in Chrome. Scan the QR code with your phone.
    *   Once logged in, you can close the script (Ctrl+C).
    *   Set `HEADLESS=true` back for normal operation if desired.
    The session data will be saved in the `CHROME_PROFILE_PATH`.

3.  **Run Application Components:**
    Open three separate terminals or use a process manager.

    *   **Flask Web Server:**
        ```bash
        python3 app.py
        ```
        This starts the web server, typically on `http://0.0.0.0:5000`.

    *   **Email Processor:**
        ```bash
        python3 email_processor.py
        ```
        This service will connect to the IMAP server and monitor for new emails.

    *   **WhatsApp Queue Processor & Sender:**
        ```bash
        python3 queue_processor.py
        ```
        This service listens to the Redis queue and sends messages via WhatsApp Web.

### Production Deployment (using PM2)

PM2 is a process manager for Node.js applications, but it can also manage Python scripts.

1.  **Install PM2 (if not already installed):**
    ```bash
    npm install pm2 -g
    ```

2.  **Start services with PM2:**
    Navigate to the `whatsapp-bridge` directory.
    ```bash
    pm2 start "python3 app.py" --name whatsapp-api
    pm2 start "python3 email_processor.py" --name email-worker
    pm2 start "python3 queue_processor.py" --name whatsapp-worker
    ```

3.  **Save PM2 process list:**
    ```bash
    pm2 save
    ```

4.  **Enable PM2 startup script (optional, to restart on server reboot):**
    ```bash
    pm2 startup
    ```
    Follow the instructions output by this command.

## Usage

*   **Web Widget**: Access the `widget.html` file through a browser (or integrate it into an existing site). It will make requests to the `/send` endpoint of `app.py`.
    *   **Important**: In `widget.html`, you **must** replace `RECIPIENT_PHONE_NUMBER` with the actual phone number you intend the widget to send messages to.
*   **Email**: Send an email to the configured IMAP account.
    *   The subject line must be in the format: `To +1234567890` (replace with the target phone number).
    *   The body of the email will be the content of the WhatsApp message.

## Troubleshooting

*   **WhatsApp QR Code Not Appearing / Selenium Issues:**
    *   Ensure Chrome and `chromedriver` are correctly installed and compatible. `chromedriver-autoinstaller` usually handles this.
    *   Disable headless mode for initial setup: In `config.py` or your environment, set `HEADLESS` to `'false'`.
        ```python
        # In whatsapp_sender.py, the check is:
        # if os.getenv('HEADLESS', 'true').lower() == 'true':
        ```
        So, ensure the environment variable `HEADLESS` is set to `false` if you are having issues with the QR code scan.
    *   Check permissions for `CHROME_PROFILE_PATH`.

*   **IMAP Connection Failing:**
    *   Verify credentials (`IMAP_USER`, `IMAP_PASSWORD`) and server details (`IMAP_SERVER`) in `config.py`.
    *   Test connection manually:
        ```python
        import imaplib
        # Make sure to source your config or set manually for testing
        # from config import Config
        mail = imaplib.IMAP4_SSL("your_imap_server") # e.g., Config.IMAP_SERVER
        try:
            mail.login("your_email_user", "your_email_password") # e.g., Config.IMAP_USER, Config.IMAP_PASSWORD
            print("IMAP login successful!")
            mail.logout()
        except Exception as e:
            print(f"IMAP login failed: {e}")
        ```

*   **Messages Not Sending / Stuck in Queue:**
    *   Check Redis connection and that the server is running.
    *   Inspect the Redis queue:
        ```bash
        redis-cli
        > LRANGE whatsapp_queue 0 -1
        ```
        This will show messages currently in the queue.
    *   Check logs from `queue_processor.py` for errors from Selenium or WhatsApp Web.
    *   Ensure the WhatsApp Web session initiated by `whatsapp_sender.py` is still active (i.e., your phone is connected and WhatsApp Web hasn't been logged out). You might need to re-scan the QR code.
```

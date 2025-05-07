# Lifetime Class Auto-Scheduler

This script automates the process of registering for specific classes at Lifetime Fitness based on predefined criteria.

## Features

- **Fetches Class Schedules:** Periodically queries the Lifetime Fitness API for upcoming class schedules within a configurable date range.
- **Filters Classes:** Filters the fetched schedule based on:
  - Keywords in the class name (inclusion and exclusion lists).
  - Day of the week (weekends vs. weekdays).
  - Time of day (e.g., only allows "Evening" classes on weekdays).
  - Whether the class is paid (`isPaidClass`).
- **Monitors Registration Windows:** Calculates when registration opens for each desired class (typically 11400 minutes / 7 days, 22 hours before the class starts).
- **Automated Registration:** Attempts to register for classes automatically when the registration window opens.
- **Retry Logic:** Implements a retry mechanism with delays for registration attempts in case of transient API errors.
- **Eligibility Checks:** Handles specific API responses indicating ineligibility (e.g., already registered for a conflicting class, "too soon" to register) to avoid unnecessary retries.
- **Notifications:** Sends SMS notifications (via email gateway) upon successful registration, registration failure (after retries), or ineligibility.
- **State Persistence:** Remembers which class registration attempts have been processed (successfully or not) in a `processed_event_ids.json` file to avoid duplicate attempts across script runs.
- **Configuration:** Uses a `.env` file for sensitive credentials and settings.
- **Logging:** Provides informative console logs about its operations.

## Prerequisites

- Python 3.x
- pip (Python package installer)
- A Lifetime Fitness account with login credentials.
- An email account (e.g., Gmail) capable of sending emails via SMTP, to be used for sending SMS notifications.
  - **Important:** If using Gmail, it's strongly recommended to generate an "App Password" for this script instead of using your main account password. Search "Google App Passwords" for instructions.

## Installation & Setup

1.  **Clone the Repository:** (If you haven't already)

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a Virtual Environment (Recommended):**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows use: .\.venv\Scripts\activate
    ```

3.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    _(Ensure `requirements.txt` includes `requests` and `python-dotenv`)_

4.  **Configure Environment Variables:**

    - Create a file named `.env` in the project's root directory.
    - Add the following key-value pairs, replacing the placeholder values with your actual information:

    ```env
    # --- Lifetime Login Credentials (used by lifetime_auth.py) ---
    LIFETIME_USERNAME="your_lifetime_login_email_or_username"
    LIFETIME_PASSWORD="your_lifetime_password"

    # --- Registration Settings (used by auto_scheduler_main.py) ---
    # Your numerical Member ID(s). For multiple, use comma-separated: "12345,67890"
    LIFETIME_MEMBER_IDS="115608390"

    # --- SMS Notification Settings (via Email Gateway) ---
    # The email address for your phone's SMS gateway.
    # Examples: 1234567890@vtext.com (Verizon), 1234567890@txt.att.net (AT&T)
    SMS_RECIPIENT_EMAIL="YOUR_PHONE_NUMBER@YOUR_CARRIER_SMS_GATEWAY.COM"

    # Email account used to send the notification emails.
    EMAIL_SENDER_ADDRESS="your_sending_email_address@example.com"

    # Password for the sender email. Use an App Password for Gmail.
    EMAIL_SENDER_PASSWORD="your_sending_email_password_or_app_password"

    # Optional: Override SMTP server/port if not using Gmail defaults
    # SMTP_SERVER="smtp.your_email_provider.com"
    # SMTP_PORT="587"
    ```

5.  **Configure Class Filters (Optional):**
    - Edit the lists `INCLUDE_IN_CLASS_NAME`, `EXCLUDE_FROM_CLASS_NAME`, `WEEKEND_DAYS`, and `ALLOWED_WEEKDAY_DAY_PARTS` at the top of `schedule_fetcher.py` to match your desired classes.

## Usage

### Running Continuously (Normal Operation)

1.  Ensure the constant `RUN_ONCE_FOR_TESTING` at the top of `auto_scheduler_main.py` is set to `False`.
2.  Activate your virtual environment (`source .venv/bin/activate`).
3.  Run the main script from the project root directory:
    ```bash
    python auto_scheduler_main.py
    ```
4.  The script will run indefinitely, logging its actions to the console. It will fetch the schedule daily and check for registration windows every second.
5.  To stop the script, press `Ctrl+C` in the terminal.

### Running Once (Testing)

1.  Set the constant `RUN_ONCE_FOR_TESTING = True` at the top of `auto_scheduler_main.py`.
2.  Run the script:
    ```bash
    python auto_scheduler_main.py
    ```
3.  The script will perform one full cycle: attempt login, attempt schedule fetch, list monitored classes, check registration windows for all fetched classes, attempt registration for at most ONE class if its window is open, and then exit.

### Fetching and Saving the Schedule Manually

1.  Ensure your `.env` file has valid login credentials.
2.  Run the `schedule_fetcher.py` script directly:
    ```bash
    python schedule_fetcher.py
    ```
3.  This will attempt to log in, fetch the schedule according to the filters defined within the script, and save the results to `schedule_output.json` (this file is ignored by git via `.gitignore`).

## Project Structure

- `auto_scheduler_main.py`: The main orchestrator script that runs the continuous loop.
- `schedule_fetcher.py`: Handles fetching and filtering the class schedule from the API.
- `registration_handler.py`: Encapsulates the two-step registration process logic.
- `notification_sender.py`: Sends SMS notifications via an email gateway.
- `lifetime_auth.py`: (Assumed) Handles authentication with the Lifetime API, returning necessary tokens.
- `lifetime_registration.py`: (Assumed) Contains the low-level functions for the individual API calls for registration steps.
- `.env`: Stores sensitive configuration (credentials, emails, etc.). **Do not commit this file.**
- `requirements.txt`: Lists Python package dependencies.
- `processed_event_ids.json`: Stores IDs of events that have already been processed. **Do not commit this file.**
- `schedule_output.json`: Output file for manually fetched schedules. **Do not commit this file.**
- `README.md`: This file.

## Disclaimer

- This script interacts with the unofficial Lifetime Fitness API. The API may change without notice, which could break the script.
- Use this script responsibly and ethically. Automating registration may be against Lifetime Fitness's terms of service.
- The author(s) are not responsible for any issues arising from the use of this script, including missed registrations or account problems.
- Ensure your notification settings (email credentials, SMS gateway) are correct.

# Lifetime Fitness Class Availability Checker

This script checks for available spots in a Life Time fitness class every 30 seconds and sends notifications when a spot becomes available.

## Prerequisites

- Python 3.6 or higher
- Required Python packages (install using `pip install -r requirements.txt`)
- (Optional) Email account for sending SMS notifications (Gmail recommended)

## Setup

1. Clone or download this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. (Optional) Configure email settings for SMS notifications:

   - Open `lifetime_class_checker.py` in a text editor
   - Set `ENABLE_EMAIL = True` to enable email notifications
   - Update the following variables:
     - `EMAIL_SENDER`: Your email address
     - `EMAIL_PASSWORD`: Your email password or app password
     - `SMTP_SERVER` and `SMTP_PORT`: If not using Gmail
     - `SMS_EMAIL`: Change if using a different carrier (currently set to Verizon)

   **Note for Gmail users**: You'll need to create an app password instead of using your regular password. Visit [Google App Passwords](https://myaccount.google.com/apppasswords) to set one up.

## Usage

Run the script from the command line:

```
python lifetime_class_checker.py
```

The script will:

- Check for available spots every 30 seconds
- Display the current status in the terminal
- Send a desktop notification when a spot becomes available
- (Optional) Send a text message via email-to-SMS gateway if enabled
- Check more frequently (every 10 seconds) once spots are available

Press `Ctrl+C` to stop the script.

## Customization

- To check a different class, update the `EVENT_ID` variable in the script with the ID of the class you want to monitor.
- You can adjust the check frequency by modifying the `time.sleep()` values in the `main()` function.
- To use a different carrier's email-to-SMS gateway, update the `SMS_EMAIL` variable. Common gateways:
  - Verizon: `number@vtext.com`
  - AT&T: `number@txt.att.net`
  - T-Mobile: `number@tmomail.net`
  - Sprint: `number@messaging.sprintpcs.com`

## How It Works

The script makes API requests to the Life Time fitness API to check if spots are available for a specific class. It uses the minimum required headers to make these requests without requiring authentication.

When a spot becomes available, the script will:

1. Display a message in the terminal
2. Send a desktop notification
3. Play a sound (on macOS)
4. (Optional) Send a text message via email-to-SMS gateway if enabled

## Notes

- This script is for personal use only and should be used responsibly.
- The script does not require authentication tokens for checking availability.
- Email notifications are disabled by default. Enable them by setting `ENABLE_EMAIL = True` and configuring your email credentials.

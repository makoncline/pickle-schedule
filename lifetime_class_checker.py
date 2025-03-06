#!/usr/bin/env python3
import requests
import time
import json
import os
import platform
import datetime
import urllib.parse
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Event ID for the class
EVENT_ID = "ZXhlcnA6MzMyYm9vazMwODQ4MDoyMDI1LTAzLTAx"

# API endpoints
REGISTRATION_URL = f"https://api.lifetimefitness.com/ux/web-schedules/v2/events/{EVENT_ID}/registration"
EVENT_DETAILS_URL = f"https://api.lifetimefitness.com/ux/web-schedules/v2/events/{EVENT_ID}"

# Email settings for text message via email gateway
SMS_EMAIL = "6015900174@vtext.com"  # Verizon email-to-SMS gateway

# Email settings - set these to empty strings to disable email notifications
EMAIL_SENDER = "sendtomakon@gmail.com"  # Gmail address
EMAIL_PASSWORD = "taog dwgb twvb axbe"  # Gmail app password
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Flag to enable/disable email notifications
ENABLE_EMAIL = True  # Email notifications are now enabled

# Minimum required headers for API requests (from incognito window)
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.8",
    "ocp-apim-subscription-key": "924c03ce573d473793e184219a6a19bd",
    "origin": "https://my.lifetime.life",
    "referer": "https://my.lifetime.life/",
    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Brave";v="132"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    # No authentication tokens needed for checking availability
}

# Function to send desktop notification
def send_notification(title, message):
    """Send a desktop notification based on the operating system."""
    try:
        if platform.system() == "Darwin":  # macOS
            os.system(f"""
                osascript -e 'display notification "{message}" with title "{title}"'
            """)
            # Also play a sound
            os.system("afplay /System/Library/Sounds/Glass.aiff")
        elif platform.system() == "Linux":
            os.system(f'notify-send "{title}" "{message}"')
        elif platform.system() == "Windows":
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=10)
        print(f"\n{title}: {message}")
    except Exception as e:
        print(f"Failed to send notification: {e}")

# Function to send text message via email
def send_text_via_email(message):
    """Send a text message via email gateway."""
    # Skip if email is disabled
    if not ENABLE_EMAIL:
        print("Email notifications are disabled. Skipping text message.")
        return False
        
    # Check if email credentials are set
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Email credentials not set. Please update EMAIL_SENDER and EMAIL_PASSWORD in the script.")
        return False
    
    try:
        # Create a plain text message instead of multipart
        msg = MIMEText(message)
        msg['From'] = EMAIL_SENDER
        msg['To'] = SMS_EMAIL
        msg['Subject'] = ""  # No subject for SMS
        
        # Keep message short for SMS
        if len(message) > 160:
            message = message[:157] + "..."
            msg.set_payload(message)
        
        # Connect to server and send
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Secure the connection
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, SMS_EMAIL, text)
        server.quit()
        
        print("Text message sent successfully via email")
        return True
    except Exception as e:
        print(f"Error sending text via email: {e}")
        return False

# Function to check class availability
def check_availability():
    """Check if spots are available in the class."""
    try:
        # Add current timestamp to headers
        current_headers = HEADERS.copy()
        current_headers["x-timestamp"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        # Get registration details
        response = requests.get(REGISTRATION_URL, headers=current_headers)
        
        if response.status_code != 200:
            print(f"Error: API returned status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        
        # Check if class has remaining spots
        remaining_spots = data.get("remainingSpots", 0)
        total_waitlisted = data.get("totalWaitlisted", 0)
        
        # Get class details for better notification
        details_response = requests.get(EVENT_DETAILS_URL, headers=current_headers)
        class_details = details_response.json() if details_response.status_code == 200 else {}
        class_name = class_details.get("name", "Pickleball Class")
        
        # Print current status
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if remaining_spots <= 0:
            print(f"[{current_time}] Class is still full. Waitlist count: {total_waitlisted}")
            return False
        else:
            notification_message = f"{remaining_spots} spot(s) now available for {class_name}! Go register now!"
            print(f"[{current_time}] SPOTS AVAILABLE! {remaining_spots} spot(s) available!")
            
            # Send desktop notification
            send_notification("Class Spot Available!", notification_message)
            
            # Add URL to register
            registration_url = f"https://my.lifetime.life/clubs/co/denver/classes/class-details.html?eventId={EVENT_ID}"
            print(f"\nRegister here: {registration_url}")
            
            # Send text message via email if enabled
            if ENABLE_EMAIL:
                # Create a shorter message to ensure the link is visible
                short_text = f"{remaining_spots} spots open!\n{registration_url}"
                send_text_via_email(short_text)
            
            return True
            
    except Exception as e:
        print(f"Error checking availability: {e}")
        return False

def main():
    """Main function to periodically check for class availability."""
    print("Starting Lifetime Class Availability Checker")
    print(f"Checking for spots in class with ID: {EVENT_ID}")
    print("Press Ctrl+C to stop the script")
    
    # Check email configuration without sending a test message
    if ENABLE_EMAIL:
        print("\nEmail notifications are enabled.")
        if not EMAIL_SENDER or not EMAIL_PASSWORD:
            print("WARNING: Email credentials not set. Please update EMAIL_SENDER and EMAIL_PASSWORD in the script.")
    else:
        print("\nEmail notifications are disabled. Only desktop notifications will be used.")
    
    try:
        while True:
            spots_available = check_availability()
            
            # If spots are available, stop the script
            if spots_available:
                print("\nSpots are available! Stopping the script.")
                print("Please go register for the class.")
                # Exit the script
                sys.exit(0)
            else:
                time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        print("\nScript stopped by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        send_notification("Script Error", f"The class checker script encountered an error: {e}")
        # Also send text for critical errors if email is enabled
        if ENABLE_EMAIL and EMAIL_SENDER and EMAIL_PASSWORD:
            send_text_via_email(f"Script Error: The class checker encountered an error")

if __name__ == "__main__":
    main() 
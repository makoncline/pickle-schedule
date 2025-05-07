#!/usr/bin/env python3

import smtplib
from email.mime.text import MIMEText

# Default SMTP settings (can be overridden by parameters)
DEFAULT_SMTP_SERVER = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587

def send_sms_notification(message_body, subject, recipient_sms_email, 
                          sender_email, sender_password, 
                          smtp_server=DEFAULT_SMTP_SERVER, smtp_port=DEFAULT_SMTP_PORT):
    """
    Sends a message (intended for SMS via email gateway) using provided credentials and settings.

    Args:
        message_body (str): The core content of the message.
        subject (str): The subject of the email (can be empty for SMS).
        recipient_sms_email (str): The email address of the SMS gateway (e.g., number@vtext.com).
        sender_email (str): The email address to send from.
        sender_password (str): The password for the sender_email.
        smtp_server (str, optional): The SMTP server address. Defaults to DEFAULT_SMTP_SERVER.
        smtp_port (int, optional): The SMTP server port. Defaults to DEFAULT_SMTP_PORT.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    if not sender_email or not sender_password or not recipient_sms_email:
        print("Notification Error: Missing sender email, password, or recipient SMS email. Cannot send.")
        return False

    try:
        msg = MIMEText(message_body)
        msg['From'] = sender_email
        msg['To'] = recipient_sms_email
        msg['Subject'] = subject
        
        # Keep message reasonably short if it's truly for SMS
        # This is a rough check, actual SMS length limits can vary by carrier and encoding
        if len(message_body) > 160: 
            print("Warning: Message body is > 160 chars, might be truncated by SMS gateway.")
            # Some gateways might truncate, others might split. No universal client-side fix.

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)
        text_to_send = msg.as_string()
        server.sendmail(sender_email, recipient_sms_email, text_to_send)
        server.quit()
        
        print(f"Notification sent successfully to {recipient_sms_email}.")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP Authentication Error sending notification: {e}")
        print("Please check sender email credentials and ensure 'less secure app access' is enabled if using Gmail and not an app password.")
        return False
    except smtplib.SMTPException as e:
        print(f"SMTP Error sending notification: {e}")
        return False
    except Exception as e:
        print(f"General Error sending notification: {e}")
        return False

if __name__ == "__main__":
    print("Testing notification_sender.py...")
    # --- Configuration for testing --- 
    # IMPORTANT: Replace with your actual test details or use environment variables for these.
    # DO NOT COMMIT REAL CREDENTIALS.
    test_recipient_sms = "YOUR_PHONE_NUMBER@YOUR_CARRIER_GATEWAY.COM" # e.g., "1234567890@vtext.com"
    test_sender_email = "YOUR_SENDER_EMAIL@gmail.com"
    test_sender_password = "YOUR_SENDER_APP_PASSWORD" # Use an App Password for Gmail
    
    test_subject = "Test Notification"
    test_message = "This is a test message from notification_sender.py! If you see this, it worked."

    print(f"Attempting to send test notification to: {test_recipient_sms}")
    print(f"From: {test_sender_email}")

    if "YOUR_PHONE_NUMBER" in test_recipient_sms or \
       "YOUR_SENDER_EMAIL" in test_sender_email or \
       "YOUR_SENDER_APP_PASSWORD" in test_sender_password:
        print("\nWARNING: Placeholder credentials detected in the test block.")
        print("Please update them in notification_sender.py to perform a real test.")
        print("Skipping actual send for safety.")
    else:
        success = send_sms_notification(
            message_body=test_message,
            subject=test_subject,
            recipient_sms_email=test_recipient_sms,
            sender_email=test_sender_email,
            sender_password=test_sender_password
            # smtp_server and smtp_port will use defaults (Gmail)
        )
        if success:
            print("Test notification believed to be sent successfully.")
        else:
            print("Test notification failed. Check errors above.") 
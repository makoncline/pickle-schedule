import requests
import logging
import os
from datetime import datetime, timezone # Added for __main__ test block

# TODO: User should set DISCORD_WEBHOOK_URL in their .env file.
# This FALLBACK_DISCORD_WEBHOOK_URL is used if the environment variable is not set.
# It's generally better for the main application to manage and pass the URL.
FALLBACK_DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1369869316471918653/65c5rpVwHM1tDiuWVSbGx3XXeW7jp9Dp6oetduuEuUOAGq3_dwIcwHS2r-nczopc0sQz"

def send_discord_notification(
    content: str = None,
    embeds: list = None, # List of embed objects
    webhook_url: str = None
) -> bool:
    """
    Sends a notification message (content and/or embeds) to a Discord webhook.

    Args:
        content: The plain text message content (max 2000 chars).
        embeds: A list of embed objects (dicts) for rich formatting (max 10 embeds).
                See: https://discord.com/developers/docs/resources/channel#embed-object
        webhook_url: The Discord webhook URL.
                     If None, tries os.getenv("DISCORD_WEBHOOK_URL"), then FALLBACK_DISCORD_WEBHOOK_URL.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL") or FALLBACK_DISCORD_WEBHOOK_URL

    if not target_url:
        logging.error("Discord webhook URL is not configured and no fallback is available.")
        return False

    if not content and not embeds:
        logging.warning("Attempted to send Discord notification with no content or embeds. This might be rejected by Discord.")
        # Discord might require at least one. Let's allow the attempt.
        # return False 

    payload = {}
    if content:
        payload["content"] = content[:2000] # Enforce Discord's limit
    if embeds:
        payload["embeds"] = embeds[:10] # Enforce Discord's limit
        # Note: Individual embed limits (e.g., description 4096 chars, 25 fields)
        # are assumed to be handled by the caller.
    
    try:
        response = requests.post(target_url, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        message_type_parts = []
        if content:
            message_type_parts.append("content")
        if embeds:
            message_type_parts.append(f"{len(embeds)} embed(s)")
        message_type_str = " and ".join(message_type_parts) if message_type_parts else "empty message"

        logging.info(f"Successfully sent Discord notification ({message_type_str}).")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Discord notification: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Discord API response: Status {e.response.status_code} - {e.response.text}")
        return False

if __name__ == '__main__':
    # Example usage:
    # Make sure to set up basicConfig for logging if running this file directly
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    
    # Test 1: Simple content message
    test_content_message = "Hello from discord_notifier.py! This is a test content message via __main__."
    if send_discord_notification(content=test_content_message):
        logging.info("Test 1 (content) Discord notification sent successfully.")
    else:
        logging.error("Failed to send Test 1 (content) Discord notification.")

    # Test 2: Simple embed message
    test_embed = {
        "title": "Test Embed from __main__",
        "description": "This is a description for the test embed. It supports **Markdown!**",
        "color": 0x00FF00, # Green
        "fields": [
            {"name": "Field 1", "value": "Value 1", "inline": True},
            {"name": "Field 2", "value": "Value 2", "inline": True}
        ],
        "footer": {"text": "Test Footer Text - via __main__"},
        "timestamp": datetime.now(timezone.utc).isoformat() # ISO 8601 timestamp
    }
    if send_discord_notification(embeds=[test_embed]): # Embeds must be a list
        logging.info("Test 2 (embed) Discord notification sent successfully.")
    else:
        logging.error("Failed to send Test 2 (embed) Discord notification.")

    # Test 3: Content and Embed
    if send_discord_notification(content="Test 3: Content accompanying an embed!", embeds=[test_embed]):
        logging.info("Test 3 (content + embed) Discord notification sent successfully.")
    else:
        logging.error("Failed to send Test 3 (content + embed) Discord notification.")
    
    # Test 4: No content and no embed (should log a warning, may fail depending on Discord API)
    # logging.info("Test 4: Attempting to send empty message (expect warning/failure)")
    # if send_discord_notification():
    #     logging.info("Test 4 (empty) Discord notification attempt was processed (check Discord).")
    # else:
    #     logging.error("Test 4 (empty) Discord notification failed as expected or URL missing.")

    # To test with a specific webhook URL different from default/env:
    # specific_url = "YOUR_OTHER_WEBHOOK_URL_FOR_TESTING"
    # if specific_url != "YOUR_OTHER_WEBHOOK_URL_FOR_TESTING": # Basic check if it's been changed
    #     if send_discord_notification(content="Test with a specific webhook URL.", webhook_url=specific_url):
    #         logging.info("Test (specific URL) Discord notification sent successfully.")
    #     else:
    #         logging.error("Failed to send test (specific URL) Discord notification.")
    # else:
    #     logging.info("Skipping specific URL test as placeholder URL is not changed.") 
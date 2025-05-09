#!/usr/bin/env python3

import json
import time
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import logging # Import logging

# --- Project Modules ---
import schedule_fetcher
# Assuming lifetime_auth.py contains perform_login directly
from lifetime_auth import perform_login 
import registration_handler
import notification_sender
import discord_notifier # Added for Discord notifications

# It's good practice to also import the lifetime_registration module here if it's needed by registration_handler
# and not handled internally by it. Based on registration_handler.py, it expects the module to be passed.
import lifetime_registration # Assuming this file exists as per original main_register.py structure

# --- Testing Flag --- 
RUN_ONCE_FOR_TESTING = False # Set to False for normal continuous operation
# ---------------------

# --- Configure Logging --- 
# Place this near the top, after imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler()  # Log to console
        # TODO: Consider adding logging.FileHandler('scheduler.log') later
    ]
)

# --- Load Environment Variables --- 
load_dotenv() # Load variables from .env file into environment

# --- Configuration --- 
# Schedule Fetcher Config (can also be kept in schedule_fetcher.py if preferred)
# These are here if we want auto_scheduler_main to override or manage them.
# For now, schedule_fetcher.py uses its own internal constants.

# Registration Config
MEMBER_IDS_TO_REGISTER = os.getenv("LIFETIME_MEMBER_IDS")
if MEMBER_IDS_TO_REGISTER:
    try:
        MEMBER_IDS_TO_REGISTER = [int(mid.strip()) for mid in MEMBER_IDS_TO_REGISTER.split(',')]
    except ValueError:
        logging.error("LIFETIME_MEMBER_IDS in .env is not a valid comma-separated list of numbers. Exiting.")
        exit()
else:
    logging.error("LIFETIME_MEMBER_IDS not found in .env file. Exiting.")
    exit()

# Notification Config - (Ensure these are set in your .env file)
SMS_RECIPIENT_EMAIL = os.getenv("SMS_RECIPIENT_EMAIL") # e.g., "1234567890@vtext.com"
EMAIL_SENDER = os.getenv("EMAIL_SENDER_ADDRESS")      # Gmail address for sending
EMAIL_PASSWORD = os.getenv("EMAIL_SENDER_PASSWORD")    # Gmail app password
# Optional: Override SMTP server/port if not using Gmail defaults
SMTP_SERVER = os.getenv("SMTP_SERVER", notification_sender.DEFAULT_SMTP_SERVER)
SMTP_PORT = int(os.getenv("SMTP_PORT", notification_sender.DEFAULT_SMTP_PORT))
# ---- Add DISCORD_WEBHOOK_URL to your .env file for Discord notifications ----
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 

# Timing Config
REGISTRATION_OPEN_MINUTES_BEFORE_EVENT = 11400  # As per user spec
SCHEDULE_CHECK_INTERVAL_SECONDS = 24 * 60 * 60    # 24 hours
REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS = 1 # Changed from 5 * 60 to 1 second

# State Management
PROCESSED_EVENTS_FILE = "processed_event_ids.json"
processed_event_ids = set()
MAX_REGISTRATION_RETRIES = 5
REGISTRATION_RETRY_DELAY_SECONDS = 2

def load_processed_events():
    """Loads the set of processed event IDs from a file."""
    global processed_event_ids
    try:
        if os.path.exists(PROCESSED_EVENTS_FILE):
            with open(PROCESSED_EVENTS_FILE, 'r') as f:
                processed_event_ids = set(json.load(f))
            logging.info(f"Loaded {len(processed_event_ids)} processed event IDs from {PROCESSED_EVENTS_FILE}")
        else:
            logging.info(f"{PROCESSED_EVENTS_FILE} not found. Starting with an empty set of processed events.")
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading {PROCESSED_EVENTS_FILE}: {e}. Starting fresh.")
        processed_event_ids = set()

def save_processed_events():
    """Saves the current set of processed event IDs to a file."""
    try:
        with open(PROCESSED_EVENTS_FILE, 'w') as f:
            json.dump(list(processed_event_ids), f) # Convert set to list for JSON serialization
        logging.debug(f"Saved {len(processed_event_ids)} processed event IDs to {PROCESSED_EVENTS_FILE}") # Debug level for frequent saves
    except IOError as e:
        logging.error(f"Error saving processed events to {PROCESSED_EVENTS_FILE}: {e}")


def main():
    """Main function to orchestrate the auto-scheduler."""
    logging.info("Starting Lifetime Auto-Scheduler...")
    if RUN_ONCE_FOR_TESTING:
        logging.info("** RUN_ONCE_FOR_TESTING mode activated. Script will exit after first schedule fetch and at most one registration attempt cycle. **")

    load_processed_events()

    # Test: print loaded configs
    logging.info("--- Configuration ---")
    logging.info(f"Member IDs to Register: {MEMBER_IDS_TO_REGISTER}")
    logging.info(f"SMS Recipient: {SMS_RECIPIENT_EMAIL}")
    logging.info(f"Email Sender: {EMAIL_SENDER}")
    logging.info(f"Reg Open Minutes Before: {REGISTRATION_OPEN_MINUTES_BEFORE_EVENT}")
    logging.info(f"Schedule Check Interval (s): {SCHEDULE_CHECK_INTERVAL_SECONDS}")
    logging.info(f"Reg Attempt Interval (s): {REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS}")
    logging.info(f"Max Reg Retries: {MAX_REGISTRATION_RETRIES}")
    logging.info(f"Reg Retry Delay (s): {REGISTRATION_RETRY_DELAY_SECONDS}")
    if DISCORD_WEBHOOK_URL:
        logging.info(f"Discord Webhook URL: Configured (will send notifications)")
    else:
        logging.info(f"Discord Webhook URL: Not configured (will skip Discord notifications)")
    logging.info("---------------------")

    if not MEMBER_IDS_TO_REGISTER or not SMS_RECIPIENT_EMAIL or not EMAIL_SENDER or not EMAIL_PASSWORD:
        logging.critical("Missing one or more required configurations in .env. Exiting.")
        return

    # Initialize variables for the main loop
    last_schedule_fetch_time = 0 # Set to 0 to trigger immediate fetch on first run
    current_schedule_activities = [] # Holds the latest fetched schedule
    jwe_token, ssoid_token = None, None

    try:
        while True:
            now_timestamp = time.time()
            now_utc_datetime = datetime.now(timezone.utc)
            current_datetime_str = now_utc_datetime.strftime("%Y-%m-%d %H:%M:%S %Z")

            logging.info(f"Main loop iteration starting...") # Removed newline for cleaner logs

            schedule_fetched_this_iteration = False
            if (now_timestamp - last_schedule_fetch_time) > SCHEDULE_CHECK_INTERVAL_SECONDS or last_schedule_fetch_time == 0:
                logging.info(f"Time to fetch new schedule (or first run).")
                
                logging.info(f"Attempting login to Lifetime Fitness...")
                # Ensure lifetime_auth.perform_login() loads credentials from .env
                jwe_token, ssoid_token = perform_login() 
                
                if not jwe_token or not ssoid_token:
                    logging.warning(f"Login failed. Cannot fetch schedule. Will retry in {REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS}s.")
                    if RUN_ONCE_FOR_TESTING and last_schedule_fetch_time == 0: # If run_once and login fails on very first try
                        logging.error("Login failed on first attempt in RUN_ONCE_FOR_TESTING mode. Exiting.")
                        break # Exit the while True loop
                    time.sleep(REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS)
                    continue # Skip to next iteration of the main loop to retry login and fetch
                
                logging.info(f"Login successful. Fetching schedule...")
                fetched_activities = schedule_fetcher.get_filtered_schedule(jwe_token, ssoid_token)
                
                if fetched_activities is not None:
                    current_schedule_activities = fetched_activities
                    logging.info(f"Successfully fetched {len(current_schedule_activities)} activities.")
                    if current_schedule_activities:
                        logging.debug("First few activities for review:") # Debug for less critical info
                        for i, act in enumerate(current_schedule_activities[:3]): # Print first 3
                            logging.debug(f"  - {act.get('date')} {act.get('start_time')}: {act.get('class_name')}")
                    last_schedule_fetch_time = now_timestamp # Update time only on successful fetch
                    
                    # --- Start Discord Notification Block for Fetched Schedule ---
                    if DISCORD_WEBHOOK_URL and current_schedule_activities and schedule_fetched_this_iteration:
                        discord_embed_lines = []
                        for activity_detail in current_schedule_activities: # Iterate over ALL fetched activities
                            class_name = activity_detail.get('class_name','N/A')
                            activity_date_str = activity_detail.get('date', 'N/A') 
                            start_time_str = activity_detail.get('start_time', 'N/A') 
                            
                            reg_opens_display_str = "N/A"
                            try:
                                start_ts_ms_str = activity_detail.get("start_timestamp")
                                if start_ts_ms_str is not None:
                                    start_dt_utc = datetime.fromtimestamp(int(start_ts_ms_str) / 1000, timezone.utc)
                                    reg_opens_dt_utc = start_dt_utc - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                                    # Format: e.g., "Mon Jan 01, 15:30 UTC"
                                    reg_opens_display_str = reg_opens_dt_utc.strftime('%a %b %d, %H:%M %Z') 
                                else:
                                    logging.warning(f"Missing start_timestamp for activity ID {activity_detail.get('id')} when creating Discord msg.")
                            except (ValueError, TypeError, AttributeError) as e_time:
                                logging.warning(f"Could not parse/format registration time for Discord msg for activity ID {activity_detail.get('id')}: {e_time}")

                            discord_embed_lines.append(f"- **{class_name}**")
                            discord_embed_lines.append(f"  - Class Time: {activity_date_str} {start_time_str}")
                            discord_embed_lines.append(f"  - Reg. Opens: {reg_opens_display_str}")

                        embed_title = f"🗓️ Schedule Update: {len(current_schedule_activities)} Classes Fetched"
                        description_header = "The latest schedule fetch includes the following classes:\n\n"
                        
                        full_description = description_header + "\n".join(discord_embed_lines)
                        
                        if len(full_description) > 4000: # Discord embed description limit is 4096
                            full_description = full_description[:4000] + "\n... (message truncated due to length)"

                        discord_embed_payload = {
                            "title": embed_title,
                            "description": full_description,
                            "color": 0x1ABC9C, # A pleasant green color (decimal)
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
                        if discord_notifier.send_discord_notification(embeds=[discord_embed_payload], webhook_url=DISCORD_WEBHOOK_URL):
                            logging.info(f"Sent Discord notification for {len(current_schedule_activities)} fetched classes.")
                        else:
                            logging.warning(f"Failed to send Discord notification for {len(current_schedule_activities)} fetched classes.")
                    # --- End Discord Notification Block ---

                    logging.info("--- Upcoming Monitored Classes (Registration Times UTC) ---")
                    monitored_count = 0
                    for activity_detail in current_schedule_activities:
                        event_id_detail = activity_detail.get("id")
                        if event_id_detail in processed_event_ids:
                            continue # Skip already processed
                        monitored_count += 1
                        start_ts_ms_str = activity_detail.get("start_timestamp")
                        try:
                            start_dt_utc = datetime.fromtimestamp(int(start_ts_ms_str) / 1000, timezone.utc)
                            reg_opens_dt_utc = start_dt_utc - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                            logging.info(f"  Watching: {activity_detail.get('class_name','N/A')} ({event_id_detail}) | Starts: {start_dt_utc.strftime('%Y-%m-%d %H:%M')} | Reg Opens: {reg_opens_dt_utc.strftime('%Y-%m-%d %H:%M')}")
                        except (ValueError, TypeError):
                            logging.warning(f"  Could not parse start_timestamp for an activity: {activity_detail.get('class_name','N/A')} ({event_id_detail})")
                    if monitored_count == 0:
                        logging.info("  No new activities to monitor from this schedule fetch (all may be processed or schedule empty).")
                    logging.info("----------------------------------------------------------")
                    schedule_fetched_this_iteration = True
                else:
                    logging.warning(f"Failed to fetch schedule. Will retry in {REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS}s.")
                    if RUN_ONCE_FOR_TESTING and last_schedule_fetch_time == 0: # If run_once and fetch fails on very first try
                        logging.error("Schedule fetch failed on first attempt in RUN_ONCE_FOR_TESTING mode. Exiting.")
                        break # Exit the while True loop
                    time.sleep(REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS)
                    continue
            else:
                logging.debug(f"Not time to fetch new schedule yet. Last fetch: {datetime.fromtimestamp(last_schedule_fetch_time if last_schedule_fetch_time > 0 else 0).strftime('%Y-%m-%d %H:%M:%S')}")

            # --- Step 9: Registration Logic (Frequent Checks) ---
            if not current_schedule_activities:
                logging.debug(f"No schedule data available to check for registrations.")
            elif not jwe_token or not ssoid_token: # Need valid tokens for registration attempts
                 logging.warning(f"Tokens are not valid for registration. Schedule fetch will re-login on next cycle.")
            else:
                logging.debug(f"Checking {len(current_schedule_activities)} activities for registration windows...")
                for activity in current_schedule_activities:
                    event_id = activity.get("id")
                    class_name = activity.get("class_name", "Unknown Class")
                    logging.debug(f"Evaluating: {class_name} ({event_id})") # Log which class is being checked

                    if event_id in processed_event_ids:
                        logging.debug(f"  Skipping already processed event: {class_name} ({event_id})")
                        continue
                    
                    try:
                        start_timestamp_ms = int(activity.get("start_timestamp"))
                        # Convert milliseconds to seconds for datetime
                        event_start_datetime_utc = datetime.fromtimestamp(start_timestamp_ms / 1000, timezone.utc)
                    except ValueError:
                        logging.error(f"Error parsing start_timestamp for {class_name} ({event_id}). Value: {activity.get('start_timestamp')}. Skipping.")
                        continue

                    registration_opens_datetime_utc = event_start_datetime_utc - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                    
                    # For debugging time comparisons:
                    # print(f"[{current_datetime_str}] Event: {class_name} ({event_id})")
                    # print(f"    Event Start UTC: {event_start_datetime_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    # print(f"    Reg Opens UTC:   {registration_opens_datetime_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    # print(f"    Current UTC:     {now_utc_datetime[0].strftime('%Y-%m-%d %H:%M:%S %Z')}")

                    if now_utc_datetime >= registration_opens_datetime_utc:
                        logging.info(f">>> Registration window OPEN for: {class_name} ({event_id}) at {activity.get('date')} {activity.get('start_time')} <<< ")
                        
                        retry_count = 0
                        registration_succeeded_this_event = False
                        final_reg_message = "Registration not fully attempted."
                        event_processed_this_cycle = False # Flag to control adding to processed_event_ids

                        while retry_count < MAX_REGISTRATION_RETRIES and not registration_succeeded_this_event:
                            logging.info(f"Attempt {retry_count + 1}/{MAX_REGISTRATION_RETRIES} for {class_name} ({event_id})")
                            
                            reg_success, reg_message, reg_data = registration_handler.attempt_event_registration(
                                event_id, 
                                MEMBER_IDS_TO_REGISTER, 
                                jwe_token, 
                                ssoid_token,
                                lifetime_registration # Pass the actual module
                            )
                            final_reg_message = reg_message # Store last message

                            if reg_success:
                                registration_succeeded_this_event = True
                                event_processed_this_cycle = True
                                logging.info(f"SUCCESS: Registered for {class_name} ({event_id}). Msg: {reg_message}")
                                subject = f"Registered for {class_name}"
                                body = f"Successfully registered for: {class_name}\nDate: {activity.get('date')} {activity.get('start_time')}\nLoc: {activity.get('location')}\nConfirm: {reg_message}"
                                
                                if notification_sender.send_sms_notification(
                                    message_body=body,
                                    subject=subject,
                                    recipient_sms_email=SMS_RECIPIENT_EMAIL,
                                    sender_email=EMAIL_SENDER,
                                    sender_password=EMAIL_PASSWORD,
                                    smtp_server=SMTP_SERVER,
                                    smtp_port=SMTP_PORT
                                ):
                                    logging.info(f"Success notification sent for {class_name}.")
                                else:
                                    logging.warning(f"Failed to send success notification for {class_name}.")
                                break # Break from retry loop on success
                            else: # Registration attempt failed
                                is_fatal_from_api = False
                                is_too_soon_from_api = False
                                notification_msg_from_api = reg_message # Default to message from handler

                                # Check for detailed Step 1 failure info in reg_data
                                if isinstance(reg_data, dict) and "response" in reg_data: 
                                    validation_info = reg_data.get("response", {}).get("validation", {})
                                    if validation_info:
                                        notification_msg_from_api = validation_info.get('notification', reg_message)
                                        final_reg_message = notification_msg_from_api # Update with more specific API message if available
                                        if validation_info.get("isFatal", False):
                                            is_fatal_from_api = True
                                            rules = validation_info.get("rules", {})
                                            if rules.get("tooSoonRule", {}).get("errorCode") == 40:
                                                is_too_soon_from_api = True
                                
                                if is_too_soon_from_api:
                                    logging.info(f"API indicates 'Too Soon' for {class_name} ({event_id}): {final_reg_message}. Will not retry in this attempt cycle. Main loop will re-evaluate.")
                                    event_processed_this_cycle = False # Do not mark as processed, let main loop try again later
                                    break # Break from retry loop, but DON'T add to processed_event_ids
                                elif is_fatal_from_api: # Other fatal errors (e.g., already registered, ineligible)
                                    logging.warning(f"Ineligible/Fatal API Error for {class_name} ({event_id}): {final_reg_message}. No more retries.")
                                    event_processed_this_cycle = True # Mark as processed
                                    subject = f"NOT Registered (Ineligible): {class_name}"
                                    body = f"Could not register for: {class_name} on {activity.get('date')} {activity.get('start_time')}.\nReason: {final_reg_message}"
                                    if notification_sender.send_sms_notification(body, subject, SMS_RECIPIENT_EMAIL, EMAIL_SENDER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT):
                                        logging.info(f"Ineligibility notification sent for {class_name}.")
                                    break # Break from retry loop
                                else: # Non-fatal, retryable error
                                    logging.warning(f"FAILED Attempt {retry_count + 1}/{MAX_REGISTRATION_RETRIES} for {class_name} ({event_id}). Msg: {final_reg_message}")
                                    retry_count += 1
                                    if retry_count < MAX_REGISTRATION_RETRIES:
                                        logging.info(f"Waiting {REGISTRATION_RETRY_DELAY_SECONDS}s before next attempt for {class_name}...")
                                        time.sleep(REGISTRATION_RETRY_DELAY_SECONDS)
                        # End of retry while loop
                        
                        if not registration_succeeded_this_event and event_processed_this_cycle: # Only if it wasn't 'too_soon' and retries exhausted for other reasons
                            logging.error(f"Registration FAILED for {class_name} ({event_id}) after {retry_count if retry_count > 0 else MAX_REGISTRATION_RETRIES} attempts. Final msg: {final_reg_message}")
                            subject = f"FAILED to Register: {class_name}"
                            body = f"Failed to register for: {class_name} on {activity.get('date')} {activity.get('start_time')} after attempts.\nLast error: {final_reg_message}"
                            if notification_sender.send_sms_notification(body, subject, SMS_RECIPIENT_EMAIL, EMAIL_SENDER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT):
                                logging.info(f"Final failure notification sent for {class_name}.")
                        
                        if event_processed_this_cycle:
                            processed_event_ids.add(event_id)
                            save_processed_events() # Save state immediately after this event is handled

                        # ---- MODIFICATION FOR RUN_ONCE_FOR_TESTING ----
                        if RUN_ONCE_FOR_TESTING:
                            logging.info(f"RUN_ONCE_FOR_TESTING: Registration attempt cycle for class '{class_name}' ({event_id}) completed. Halting further class checks in this run.")
                            # The outer loop's RUN_ONCE_FOR_TESTING check will handle exiting the script.
                            break # Break from this for loop (iterating through activities)
                        # ---------------------------------------------
                    else:
                        logging.debug(f"  Registration window not yet open for {class_name} ({event_id}). Opens: {registration_opens_datetime_utc.strftime('%Y-%m-%d %H:%M')}")

            # --- Check for RUN_ONCE_FOR_TESTING exit condition ---
            if RUN_ONCE_FOR_TESTING:
                # This condition will be met after the schedule fetch attempt (successful or not if it was the first) 
                # and after iterating through activities (potentially breaking early if one registration was triggered).
                if schedule_fetched_this_iteration or (last_schedule_fetch_time != 0 and not schedule_fetched_this_iteration) or (last_schedule_fetch_time == 0) :
                    logging.info("RUN_ONCE_FOR_TESTING: Processing cycle complete. Exiting.")
                    break # Exit the main while True loop

            logging.debug(f"Loop finished. Sleeping for {REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS}s...")
            save_processed_events()
            time.sleep(REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("Script stopped by user.")
    except Exception as e: # Catch any other unexpected exceptions in the main loop
        logging.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        save_processed_events() # Ensure state is saved on exit
        logging.info("Exiting Lifetime Auto-Scheduler.")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3

import json
import time
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import logging # Import logging
import pytz # Added for timezone conversion
import sys # Added for explicit stdout targeting

# --- Project Modules ---
import schedule_fetcher
# Assuming lifetime_auth.py contains perform_login directly
from lifetime_auth import perform_login 
import registration_handler
import discord_notifier # Added for Discord notifications

# It's good practice to also import the lifetime_registration module here if it's needed by registration_handler
# and not handled internally by it. Based on registration_handler.py, it expects the module to be passed.
import lifetime_registration # Assuming this file exists as per original main_register.py structure

# --- Timezone Configuration ---
MOUNTAIN_TZ = pytz.timezone('America/Denver')

# --- Helper Function for Timedelta Formatting ---
def format_timedelta_to_human_readable(delta):
    """Converts a timedelta object to a human-readable string like '2d 3h 5m' or 'Window Open/Passed'."""
    if delta.total_seconds() <= 0:
        return "Window Open/Passed"

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or (days == 0 and hours == 0): # Show minutes if it's the smallest unit or only unit
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "Now"

# --- Custom Logging Formatter for Mountain Time ---
class MountainTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, timezone.utc)
        dt_mt = dt.astimezone(MOUNTAIN_TZ)
        if datefmt:
            s = dt_mt.strftime(datefmt)
        else:
            try:
                s = dt_mt.isoformat(timespec='milliseconds')
            except TypeError:
                s = dt_mt.isoformat()
        return s

# --- Configure Logging --- 
# Place this near the top, after imports and MOUNTAIN_TZ definition
log_formatter = MountainTimeFormatter(
    fmt='%(asctime)s [%(levelname).1s]\n    %(message)s', # Log message on a new, indented line
    datefmt='%Y-%m-%d %I:%M:%S %p %Z' # Changed to AM/PM
)
console_handler = logging.StreamHandler(sys.stdout) # Explicitly target sys.stdout
console_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler]
)

# --- Testing Flag --- 
RUN_ONCE_FOR_TESTING = False # Set to False for normal continuous operation
# ---------------------

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
# ---- Add DISCORD_WEBHOOK_URL to your .env file for Discord notifications ----
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 

# Timing Config
REGISTRATION_OPEN_MINUTES_BEFORE_EVENT = 11400  # As per user spec
SCHEDULE_CHECK_INTERVAL_SECONDS = 24 * 60 * 60    # 24 hours
# REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS = 1 # Replaced by dynamic sleep
# --- New Windowed Registration Attempt Config ---
REGISTRATION_ATTEMPT_LEAD_TIME_SECONDS = 2  # How many seconds before official open time to start first attempt
REGISTRATION_ATTEMPT_DURATION_SECONDS = 120 # Total duration for active registration attempts
REGISTRATION_RETRY_INTERVAL_WITHIN_WINDOW_SECONDS = 2 # Interval between attempts within the active window
CATCH_UP_ATTEMPT_DURATION_SECONDS = 10 # Duration to attempt if ideal window already passed for a new event

# --- Dynamic Sleep Configuration ---
MIN_SLEEP_INTERVAL_S = 1.0  # Minimum sleep time in seconds
DEFAULT_MAX_SLEEP_INTERVAL_S = 15 * 60.0  # Default maximum sleep time (e.g., 15 minutes)
INITIAL_FETCH_RETRY_INTERVAL_S = 60.0    # Sleep time if initial login/fetch fails (e.g., 60 seconds)

# State Management
PROCESSED_EVENTS_FILE = "processed_event_ids.json"
processed_event_id_set = set() # Renamed from processed_event_ids
processed_event_details_list = [] # New list to store detailed records
# MAX_REGISTRATION_RETRIES = 5 # Replaced by windowed attempt logic
# REGISTRATION_RETRY_DELAY_SECONDS = 2 # Replaced by REGISTRATION_RETRY_INTERVAL_WITHIN_WINDOW_SECONDS

def load_processed_events():
    """Loads processed event records from a file.
    Populates processed_event_id_set for quick lookups and
    processed_event_details_list for storing/saving detailed records.
    """
    global processed_event_id_set, processed_event_details_list
    processed_event_id_set = set()    # Initialize
    processed_event_details_list = [] # Initialize

    try:
        if os.path.exists(PROCESSED_EVENTS_FILE):
            with open(PROCESSED_EVENTS_FILE, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                if all(isinstance(item, dict) for item in data): # New format: list of dicts
                    processed_event_details_list = data
                    for item in processed_event_details_list:
                        if 'event_id' in item and item.get('status') != "SKIPPED_WINDOW_ALREADY_PASSED": # Ensure not to add this status back if it was somehow there
                            processed_event_id_set.add(item['event_id'])
                    logging.info(f"Loaded {len(processed_event_details_list)} detailed processed event records from {PROCESSED_EVENTS_FILE}.")
                elif all(isinstance(item, str) for item in data): # Old format: list of strings
                    processed_event_id_set = set(data)
                    # Convert old format to minimal new format entries
                    for old_event_id in processed_event_id_set:
                        # Check if a detailed record might already exist from a partial previous conversion (unlikely but safe)
                        if not any(d.get('event_id') == old_event_id for d in processed_event_details_list):
                            minimal_record = {
                                "event_id": old_event_id,
                                "class_name": "N/A (Old Record)",
                                "event_datetime_mt": "N/A",
                                "registration_opens_mt": "N/A",
                                "status": "IMPORTED_OLD_FORMAT",
                                "message": "Event ID imported from previous plain list format.",
                                "processed_timestamp_mt": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M:%S %p %Z')
                            }
                            processed_event_details_list.append(minimal_record)
                    logging.info(f"Loaded {len(processed_event_id_set)} event IDs from old format in {PROCESSED_EVENTS_FILE}. Converted to minimal detailed records. File will be updated to new format on save.")
                else: # Mixed or unknown list content
                    logging.warning(f"{PROCESSED_EVENTS_FILE} contains a list with mixed or unknown item types. Starting with empty processed records.")
            else: # Not a list
                logging.warning(f"{PROCESSED_EVENTS_FILE} does not contain a list. Starting with empty processed records.")
        else:
            logging.info(f"{PROCESSED_EVENTS_FILE} not found. Starting with empty processed records.")
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading or parsing {PROCESSED_EVENTS_FILE}: {e}. Starting fresh.")
        processed_event_id_set = set()
        processed_event_details_list = []

def save_processed_events():
    """Saves the current list of detailed processed event records to a file."""
    global processed_event_details_list
    try:
        with open(PROCESSED_EVENTS_FILE, 'w') as f:
            json.dump(processed_event_details_list, f, indent=4) # Save the list of dicts with indent
        logging.debug(f"Saved {len(processed_event_details_list)} detailed processed event records to {PROCESSED_EVENTS_FILE}")
    except IOError as e:
        logging.error(f"Error saving detailed processed events to {PROCESSED_EVENTS_FILE}: {e}")

# --- Helper function to add event to processed records ---
def _add_event_to_processed_records(event_id, class_name, activity_data, status, message, attempts_in_window=None):
    global processed_event_details_list, processed_event_id_set

    # Try to find an existing record to update
    existing_record = None
    for record_item in processed_event_details_list:
        if record_item.get('event_id') == event_id:
            existing_record = record_item
            break

    current_timestamp_mt = datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M:%S %p %Z')

    if existing_record:
        logging.debug(f"Updating existing detailed record for event {event_id} ({class_name}). Old status: {existing_record.get('status')}, New status: {status}")
        existing_record["class_name"] = class_name # Update class name in case it changed (unlikely for same ID but good practice)
        existing_record["status"] = status
        existing_record["message"] = message
        existing_record["processed_timestamp_mt"] = current_timestamp_mt
        if attempts_in_window is not None:
            existing_record["attempts_made_in_window"] = attempts_in_window
        else:
            # If new status doesn't imply attempts, remove the key if it exists from a previous status
            existing_record.pop("attempts_made_in_window", None)
        
        # Ensure event/reg times are present or updated if they were N/A
        if existing_record.get("event_datetime_mt", "N/A") == "N/A" or existing_record.get("registration_opens_mt", "N/A") == "N/A":
            try:
                start_ts_ms_upd = int(activity_data.get("start_timestamp"))
                event_start_utc_upd = datetime.fromtimestamp(start_ts_ms_upd / 1000, timezone.utc)
                existing_record["event_datetime_mt"] = event_start_utc_upd.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                reg_opens_utc_upd = event_start_utc_upd - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                existing_record["registration_opens_mt"] = reg_opens_utc_upd.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
            except (ValueError, TypeError, AttributeError) as e_upd:
                logging.warning(f"Could not format event/reg times while updating record for {event_id}: {e_upd}")
    else:
        logging.debug(f"Adding new detailed record for event {event_id} ({class_name}). Status: {status}")
        event_start_mt_str = "N/A"
        reg_opens_mt_str = "N/A"
        try:
            start_ts_ms = int(activity_data.get("start_timestamp"))
            event_start_utc = datetime.fromtimestamp(start_ts_ms / 1000, timezone.utc)
            event_start_mt_str = event_start_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
            
            reg_opens_utc = event_start_utc - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
            reg_opens_mt_str = reg_opens_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
        except (ValueError, TypeError, AttributeError) as e:
            logging.warning(f"Could not format event/reg times for new processed record of {event_id} ({class_name}): {e}")

        new_record = {
            "event_id": event_id,
            "class_name": class_name,
            "event_datetime_mt": event_start_mt_str,
            "registration_opens_mt": reg_opens_mt_str,
            "status": status,
            "message": message,
            "processed_timestamp_mt": current_timestamp_mt
        }
        if attempts_in_window is not None:
            new_record["attempts_made_in_window"] = attempts_in_window
        processed_event_details_list.append(new_record)

    processed_event_id_set.add(event_id) # Crucial to keep the set in sync for quick lookups
    
    save_processed_events() # Save immediately after adding/updating a record
    logging.info(f"Event {event_id} ({class_name}) processed. Status: {status}. Record saved/updated.")


def main():
    """Main function to orchestrate the auto-scheduler."""
    logging.info("Starting Lifetime Auto-Scheduler...")
    if RUN_ONCE_FOR_TESTING:
        logging.info("** RUN_ONCE_FOR_TESTING mode activated. Script will exit after first schedule fetch and at most one registration attempt cycle. **")

    load_processed_events()

    # Test: print loaded configs
    logging.info("--- Configuration ---")
    logging.info(f"Member IDs to Register: {MEMBER_IDS_TO_REGISTER}")
    logging.info(f"Reg Open Minutes Before: {REGISTRATION_OPEN_MINUTES_BEFORE_EVENT}")
    logging.info(f"Schedule Check Interval (s): {SCHEDULE_CHECK_INTERVAL_SECONDS}")
    # logging.info(f"Reg Attempt Interval (s): {REGISTRATION_ATTEMPT_CHECK_INTERVAL_SECONDS}")
    logging.info(f"Reg Attempt Lead Time (s): {REGISTRATION_ATTEMPT_LEAD_TIME_SECONDS}")
    logging.info(f"Reg Attempt Duration (s): {REGISTRATION_ATTEMPT_DURATION_SECONDS}")
    logging.info(f"Reg Retry Interval in Window (s): {REGISTRATION_RETRY_INTERVAL_WITHIN_WINDOW_SECONDS}")
    logging.info(f"Catch-up Attempt Duration (s): {CATCH_UP_ATTEMPT_DURATION_SECONDS}")
    if DISCORD_WEBHOOK_URL:
        logging.info(f"Discord Webhook URL: Configured (will send notifications)")
    else:
        logging.info(f"Discord Webhook URL: Not configured (will skip Discord notifications)")
    logging.info("---------------------")

    # --- Startup Notification ---
    if DISCORD_WEBHOOK_URL:
        startup_embed = {
            "title": "🚀 Lifetime Auto-Scheduler Started",
            "description": "The scheduling and registration bot has been initialized.",
            "color": 0x5865F2, # Discord Blurple
            "timestamp": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).isoformat()
        }
        if discord_notifier.send_discord_notification(embeds=[startup_embed], webhook_url=DISCORD_WEBHOOK_URL):
            logging.info("Sent startup notification to Discord.")
        else:
            logging.warning("Failed to send startup notification to Discord.")
    # --- End Startup Notification ---

    if not MEMBER_IDS_TO_REGISTER:
        logging.critical("Missing LIFETIME_MEMBER_IDS in .env. Exiting.")
        return

    # Initialize variables for the main loop
    last_schedule_fetch_time = 0 # Set to 0 to trigger immediate fetch on first run
    current_schedule_activities = [] # Holds the latest fetched schedule
    jwe_token, ssoid_token = None, None

    try:
        while True:
            now_timestamp = time.time()
            now_utc_datetime = datetime.now(timezone.utc)
            current_datetime_mt_str = now_utc_datetime.astimezone(MOUNTAIN_TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")

            log_message_parts = [f"Main loop iteration starting at {current_datetime_mt_str}."]
            
            registration_queue_logging = []
            if current_schedule_activities: # Only build queue if there are activities
                for activity_detail in current_schedule_activities:
                    event_id_detail = activity_detail.get("id")
                    if event_id_detail not in processed_event_id_set:
                        class_name_q = activity_detail.get('class_name', 'N/A')
                        event_start_str_q_mt = "N/A"
                        reg_opens_str_q_mt = "N/A"
                        time_until_reg_str = "N/A"
                        try:
                            start_ts_ms_str = activity_detail.get("start_timestamp")
                            if start_ts_ms_str:
                                start_dt_utc_q = datetime.fromtimestamp(int(start_ts_ms_str) / 1000, timezone.utc)
                                event_start_str_q_mt = start_dt_utc_q.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                                
                                reg_opens_dt_utc_q = start_dt_utc_q - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                                reg_opens_str_q_mt = reg_opens_dt_utc_q.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                                
                                # Calculate time until registration opens
                                time_delta_to_reg = reg_opens_dt_utc_q - now_utc_datetime
                                time_until_reg_str = format_timedelta_to_human_readable(time_delta_to_reg)
                                
                        except (ValueError, TypeError) as e_q_time:
                            logging.debug(f"Error formatting time for queue log (event {event_id_detail}): {e_q_time}")
                        registration_queue_logging.append(f"  - {class_name_q} ({event_id_detail}) | Event: {event_start_str_q_mt} | Reg. Opens: {reg_opens_str_q_mt} | Until Reg: {time_until_reg_str}")
            
            if registration_queue_logging:
                log_message_parts.append(f"Upcoming Registrations ({len(registration_queue_logging)} items):") # Changed title
                log_message_parts.extend(registration_queue_logging)
            else:
                log_message_parts.append("Upcoming Registrations: Empty.") # Changed title
            
            logging.info("\n".join(log_message_parts))

            schedule_fetched_this_iteration = False
            if (now_timestamp - last_schedule_fetch_time) > SCHEDULE_CHECK_INTERVAL_SECONDS or last_schedule_fetch_time == 0:
                logging.info(f"Time to fetch new schedule (or first run).")
                
                logging.info(f"Attempting login to Lifetime Fitness...")
                # Ensure lifetime_auth.perform_login() loads credentials from .env
                jwe_token, ssoid_token = perform_login() 
                
                if not jwe_token or not ssoid_token:
                    logging.warning(f"Login failed. Cannot fetch schedule. Will retry shortly.")
                    if RUN_ONCE_FOR_TESTING and last_schedule_fetch_time == 0:
                        logging.error("Login failed on first attempt in RUN_ONCE_FOR_TESTING mode. Exiting.")
                        break
                    time.sleep(INITIAL_FETCH_RETRY_INTERVAL_S)
                    continue
                
                logging.info(f"Login successful. Fetching schedule...")
                fetched_activities = schedule_fetcher.get_filtered_schedule(jwe_token, ssoid_token)
                
                if fetched_activities is not None:
                    current_schedule_activities = fetched_activities
                    logging.info(f"Successfully fetched {len(current_schedule_activities)} activities.")
                    if current_schedule_activities:
                        logging.debug("First few activities for review:") # Debug for less critical info
                        for i, act in enumerate(current_schedule_activities[:3]): # Print first 3
                            logging.debug(f"  - {act.get('date')} {act.get('start_time')}: {act.get('class_name')}")
                    last_schedule_fetch_time = now_timestamp
                    schedule_fetched_this_iteration = True
                    
                    # --- Start Discord Notification Block for Fetched Schedule ---
                    if DISCORD_WEBHOOK_URL and current_schedule_activities: # Removed schedule_fetched_this_iteration check here as it's now always true if we get here
                        discord_embed_lines = []
                        for activity_detail in current_schedule_activities: 
                            event_id_disc = activity_detail.get('id', 'N/A')
                            if event_id_disc in processed_event_id_set: # Use renamed set
                                continue # Skip already processed events

                            class_name_disc = activity_detail.get('class_name','N/A')
                            # event_id_disc is already defined above
                            
                            event_start_str_disc_mt = "N/A"
                            reg_opens_display_str_disc_mt = "N/A"
                            time_until_reg_disc_str = "N/A"

                            try:
                                start_ts_ms_str_disc = activity_detail.get("start_timestamp")
                                if start_ts_ms_str_disc is not None:
                                    start_dt_utc_disc = datetime.fromtimestamp(int(start_ts_ms_str_disc) / 1000, timezone.utc)
                                    event_start_str_disc_mt = start_dt_utc_disc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                                    
                                    reg_opens_dt_utc_disc = start_dt_utc_disc - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                                    reg_opens_display_str_disc_mt = reg_opens_dt_utc_disc.astimezone(MOUNTAIN_TZ).strftime('%a %b %d, %I:%M %p %Z')
                                    
                                    # Calculate time until registration for Discord message
                                    # now_utc_datetime is available from the start of the main loop iteration
                                    time_delta_to_reg_disc = reg_opens_dt_utc_disc - now_utc_datetime
                                    time_until_reg_disc_str = format_timedelta_to_human_readable(time_delta_to_reg_disc)
                                else:
                                    logging.warning(f"Missing start_timestamp for Discord msg (event ID {event_id_disc}).")
                            except (ValueError, TypeError, AttributeError) as e_disc_time:
                                logging.warning(f"Could not parse/format reg time for Discord msg (event ID {event_id_disc}): {e_disc_time}")
                            
                            # Constructing the line similar to the detailed log format
                            line_parts = [
                                f"- **{class_name_disc}** ({event_id_disc})",
                                f"  - Starts: {event_start_str_disc_mt}",
                                f"  - Reg. Opens: {reg_opens_display_str_disc_mt} (Until Reg: {time_until_reg_disc_str})"
                            ]
                            discord_embed_lines.append("\n".join(line_parts)) # Join parts for a multi-line entry per class

                        if discord_embed_lines: # Only send if there are new (unprocessed) classes
                            embed_title_disc = f"🗓️ Schedule Update: {len(discord_embed_lines)} New Classes Fetched"
                            description_header_disc = "The latest schedule fetch includes the following new classes:\\n"
                            
                            full_description_disc = description_header_disc + "\n".join(discord_embed_lines)
                            
                            if len(full_description_disc) > 4000: # Discord embed description limit is 4096
                                full_description_disc = full_description_disc[:4000] + "\n... (message truncated due to length)"

                            discord_embed_payload = {
                                "title": embed_title_disc,
                                "description": full_description_disc,
                                "color": 0x1ABC9C, # A pleasant green color (decimal)
                                "timestamp": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).isoformat()
                            }
                            
                            if discord_notifier.send_discord_notification(embeds=[discord_embed_payload], webhook_url=DISCORD_WEBHOOK_URL):
                                logging.info(f"Sent Discord notification for {len(discord_embed_lines)} new fetched classes.")
                            else:
                                logging.warning(f"Failed to send Discord notification for {len(discord_embed_lines)} new fetched classes.")
                        else:
                            logging.info("Schedule fetched, but all activities were already processed or filtered out. No 'Schedule Update' Discord notification sent.")
                    # --- End Discord Notification Block ---

                    logging.info("--- Upcoming Monitored Classes (Registration Times in Mountain Time) ---")
                    monitored_count = 0
                    for activity_detail in current_schedule_activities:
                        event_id_detail_mon = activity_detail.get("id")
                        if event_id_detail_mon in processed_event_id_set: # Use renamed set
                            continue
                        monitored_count += 1
                        class_name_mon = activity_detail.get('class_name','N/A')
                        start_dt_mt_str = "N/A"
                        reg_opens_dt_mt_str = "N/A"
                        time_until_reg_mon_str = "N/A"
                        try:
                            start_ts_ms_str_mon = activity_detail.get("start_timestamp")
                            if start_ts_ms_str_mon:
                                start_dt_utc_mon = datetime.fromtimestamp(int(start_ts_ms_str_mon) / 1000, timezone.utc)
                                start_dt_mt_str = start_dt_utc_mon.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                                
                                reg_opens_dt_utc_mon = start_dt_utc_mon - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                                reg_opens_dt_mt_str = reg_opens_dt_utc_mon.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                                
                                # Calculate time until registration for monitored classes
                                time_delta_to_reg_mon = reg_opens_dt_utc_mon - now_utc_datetime # now_utc_datetime is from the start of the current main loop iteration
                                time_until_reg_mon_str = format_timedelta_to_human_readable(time_delta_to_reg_mon)
                                
                            logging.info(f"  Watching: {class_name_mon} ({event_id_detail_mon}) | Starts: {start_dt_mt_str} | Reg Opens: {reg_opens_dt_mt_str} | Until Reg: {time_until_reg_mon_str}")
                        except (ValueError, TypeError):
                            logging.warning(f"  Could not parse/format times for monitored class: {class_name_mon} ({event_id_detail_mon})")
                    if monitored_count == 0:
                        logging.info("  No new activities to monitor (all may be processed or schedule empty).")
                    logging.info("----------------------------------------------------------")
                else:
                    logging.warning(f"Failed to fetch schedule. Will retry shortly.")
                    schedule_fetched_this_iteration = False # Ensure it's false if fetch failed
                    if RUN_ONCE_FOR_TESTING and last_schedule_fetch_time == 0:
                        logging.error("Schedule fetch failed on first attempt (RUN_ONCE_FOR_TESTING). Exiting.")
                        break
                    time.sleep(INITIAL_FETCH_RETRY_INTERVAL_S)
                    continue
            else:
                # If not fetching schedule, ensure this is False so Discord notification for new schedule doesn't re-trigger without a new fetch.
                schedule_fetched_this_iteration = False 
                last_fetch_dt_mt_str = datetime.fromtimestamp(last_schedule_fetch_time if last_schedule_fetch_time > 0 else 0).astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                logging.debug(f"Not time to fetch new schedule. Last fetch: {last_fetch_dt_mt_str}")

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

                    if event_id in processed_event_id_set: # Use renamed set
                        logging.debug(f"  Skipping already processed event: {class_name} ({event_id})")
                        continue
                    
                    try:
                        start_timestamp_ms = int(activity.get("start_timestamp"))
                        # Convert milliseconds to seconds for datetime
                        event_start_datetime_utc = datetime.fromtimestamp(start_timestamp_ms / 1000, timezone.utc)
                    except (ValueError, TypeError): # Added TypeError for None if get() returns None and int() fails
                        logging.error(f"Error parsing start_timestamp for {class_name} ({event_id}). Value: {activity.get('start_timestamp')}. Skipping.")
                        continue

                    registration_opens_datetime_utc = event_start_datetime_utc - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                    
                    # --- New Windowed Attempt Logic ---
                    attempt_window_start_utc = registration_opens_datetime_utc - timedelta(seconds=REGISTRATION_ATTEMPT_LEAD_TIME_SECONDS)
                    attempt_window_end_utc = attempt_window_start_utc + timedelta(seconds=REGISTRATION_ATTEMPT_DURATION_SECONDS)
                    
                    current_processing_time_utc = datetime.now(timezone.utc) # Get current time for this event's evaluation

                    if current_processing_time_utc < attempt_window_start_utc:
                        # Not yet time to start trying for this one. Dynamic sleep will handle waking up.
                        attempt_window_start_mt_str = attempt_window_start_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M:%S %p %Z')
                        logging.debug(f"  Attempt window for {class_name} ({event_id}) not yet open. Starts: {attempt_window_start_mt_str}")
                        continue

                    # If we reach here, it means: current_processing_time_utc >= attempt_window_start_utc
                    # So, it's time for lead-in, or official open, or past official open. We should attempt.

                    # Determine the actual end time for our attempt loop for this event, this cycle.
                    ideal_attempt_window_end_utc = attempt_window_start_utc + timedelta(seconds=REGISTRATION_ATTEMPT_DURATION_SECONDS)
                    current_loop_attempt_window_end_utc = ideal_attempt_window_end_utc
                    active_window_duration_for_message = REGISTRATION_ATTEMPT_DURATION_SECONDS
                    window_type_log_msg = "ideal"

                    if current_processing_time_utc >= ideal_attempt_window_end_utc:
                        # Ideal window has passed. This is a catch-up scenario for a (likely) newly seen event.
                        current_loop_attempt_window_end_utc = current_processing_time_utc + timedelta(seconds=CATCH_UP_ATTEMPT_DURATION_SECONDS)
                        active_window_duration_for_message = CATCH_UP_ATTEMPT_DURATION_SECONDS
                        window_type_log_msg = "catch-up"
                        logging.info(f"Ideal attempt window for {class_name} ({event_id}) has passed. Initiating {window_type_log_msg} attempts.")

                    activity_date_mt = event_start_datetime_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d')
                    activity_time_mt = event_start_datetime_utc.astimezone(MOUNTAIN_TZ).strftime('%I:%M %p %Z')
                    loop_attempt_window_end_mt_str = current_loop_attempt_window_end_utc.astimezone(MOUNTAIN_TZ).strftime('%I:%M:%S %p %Z')
                    logging.info(f">>> Active registration attempt window ({window_type_log_msg}) for: {class_name} ({event_id}) at {activity_date_mt} {activity_time_mt}. Trying until {loop_attempt_window_end_mt_str}. <<< ")
                    
                    retry_count_in_window = 0
                    registration_succeeded_this_event = False
                    final_reg_message = "Registration attempts concluded for the window." # Default message
                    event_processed_this_cycle = False # Will be True if success, fatal, or window ends unsuccessfully

                    # Define the specific conflict message text - already defined globally, but good to remember it's used here
                    conflict_message_text = "Sorry, we are unable to complete your reservation. You already have a reservation at this time."

                    while datetime.now(timezone.utc) < current_loop_attempt_window_end_utc and not registration_succeeded_this_event:
                        current_attempt_time_for_loop_utc = datetime.now(timezone.utc)
                        # Double check if window closed while in previous logic or short sleep
                        if current_attempt_time_for_loop_utc >= current_loop_attempt_window_end_utc:
                            logging.info(f"Attempt window for {class_name} ({event_id}) closed during retry logic ({window_type_log_msg} window).")
                            break

                        logging.info(f"Attempt {retry_count_in_window + 1} (in {window_type_log_msg} window) for {class_name} ({event_id}) at {current_attempt_time_for_loop_utc.astimezone(MOUNTAIN_TZ).strftime('%I:%M:%S %p %Z')}")
                        
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
                            
                            # Call helper to add/save detailed record
                            _add_event_to_processed_records(
                                event_id, 
                                class_name, 
                                activity, # Pass the activity dictionary
                                "SUCCESS", 
                                reg_message
                            )
                            
                            # --- Discord Notification for Success ---
                            if DISCORD_WEBHOOK_URL:
                                embed_payload_success = {
                                    "title": f"✅ Successfully Registered: {class_name}",
                                    "description": f"**Class:** {class_name}\n**Event ID:** {event_id}\n**Date:** {activity.get('date')} {activity.get('start_time')}\n**Location:** {activity.get('location', 'N/A')}\n**Message:** {reg_message}",
                                    "color": 0x2ECC71, # Green
                                    "timestamp": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).isoformat()
                                }
                                if discord_notifier.send_discord_notification(embeds=[embed_payload_success], webhook_url=DISCORD_WEBHOOK_URL):
                                    logging.info(f"Sent Discord success notification for {class_name}.")
                                else: # Corrected indentation from original code for this else
                                    logging.warning(f"Failed to send Discord success notification for {class_name}.")
                            # --- End Discord Notification ---
                            break # Break from retry loop on success
                        else: # Registration attempt failed
                            is_fatal_from_api = False 
                            is_too_soon_from_api = False 
                            notification_msg_from_api = reg_message 

                            if isinstance(reg_data, dict) and "validation" in reg_data: 
                                validation_info = reg_data.get("validation", {}) 
                                if validation_info:
                                    notification_msg_from_api = validation_info.get('notification', reg_message)
                                    final_reg_message = notification_msg_from_api 
                                    
                                    if "Registration will be open on" in notification_msg_from_api:
                                        is_too_soon_from_api = True
                                        logging.info(f"API indicates 'Too Soon' (specific message) for {class_name} ({event_id}): \"{notification_msg_from_api}\"")
                                        # Log event/reg/current times for context
                                        logging.info(f"  Event Start (MT):              {event_start_datetime_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')}")
                                        logging.info(f"  Official Reg. Window Opens (MT): {registration_opens_datetime_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')}")
                                        logging.info(f"  Current Attempt Time (MT):       {current_attempt_time_for_loop_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')}")
                                    
                                    else: 
                                        is_reservation_conflict = conflict_message_text in notification_msg_from_api
                                        if validation_info.get("isFatal", False) or is_reservation_conflict:
                                            if is_reservation_conflict:
                                                is_fatal_from_api = True 
                                                logging.info(f"Identified reservation conflict for {class_name} ({event_id}): '{notification_msg_from_api}'. Treating as fatal.")
                                            elif validation_info.get("isFatal", False): 
                                                rules = validation_info.get("rules", {})
                                                if rules.get("tooSoonRule", {}).get("errorCode") == 40: # Old tooSoonRule
                                                    is_too_soon_from_api = True # Reclassify as "too soon" for our logic
                                                    logging.info(f"API indicates 'Too Soon' (errorCode 40) for {class_name} ({event_id}). Message: \"{notification_msg_from_api}\"")
                                                else:
                                                    is_fatal_from_api = True # Truly fatal
                                        # If not a conflict and API doesn't say isFatal, it might be a retryable error. is_fatal/is_too_soon remain False.
                                else: 
                                    logging.warning(f"Could not parse detailed validation info from reg_data (empty validation_info dict) for {class_name} ({event_id}). reg_data: {reg_data}")
                            else: 
                                logging.warning(f"Could not parse detailed validation info from reg_data (bad structure or key missing) for {class_name} ({event_id}). reg_data: {reg_data}")
                            
                            # --- Decision point based on flags ---
                            if is_fatal_from_api:
                                logging.warning(f"Ineligible/Fatal API Error for {class_name} ({event_id}) during {window_type_log_msg} window: {final_reg_message}. No more retries for this event.")
                                event_processed_this_cycle = True # Mark for adding to processed records
                                
                                status_str = "FATAL_API_ERROR"
                                if "You are already registered" in final_reg_message:
                                    status_str = "FATAL_ALREADY_REGISTERED"
                                elif conflict_message_text in final_reg_message: # Check if it was a reservation conflict
                                    status_str = "FATAL_RESERVATION_CONFLICT"
                                
                                _add_event_to_processed_records(
                                    event_id,
                                    class_name,
                                    activity, # Pass the activity dictionary
                                    status_str,
                                    final_reg_message
                                )
                                
                                # --- Discord Notification for Fatal/Ineligible Error ---
                                if DISCORD_WEBHOOK_URL:
                                    embed_payload_fatal = {
                                        "title": f"⚠️ Registration Not Processed: {class_name}",
                                        "description": f"Could not register for **{class_name}** (Event ID: {event_id}) on {activity.get('date')} {activity.get('start_time')}.\n**Reason:** {final_reg_message}",
                                        "color": 0xF39C12, # Orange
                                        "timestamp": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).isoformat()
                                    }
                                    if discord_notifier.send_discord_notification(embeds=[embed_payload_fatal], webhook_url=DISCORD_WEBHOOK_URL):
                                        logging.info(f"Sent Discord fatal/ineligible notification for {class_name}.")
                                    else:
                                        logging.warning(f"Failed to send Discord fatal/ineligible notification for {class_name}.")
                                # --- End Discord Notification ---
                                break # Break from retry loop, as it's a terminal state for this event
                            else:
                                # Not fatal, so it's either "too soon" or another retryable error.
                                # Increment attempt counter for any non-fatal failed attempt.
                                retry_count_in_window += 1

                                if is_too_soon_from_api:
                                    logging.info(f"API indicates 'Too Soon' for {class_name} ({event_id}) on attempt {retry_count_in_window} in {window_type_log_msg} window. Message: \"{final_reg_message}\". Continuing attempts if window open.")
                                else:
                                    # Other retryable error
                                    logging.warning(f"FAILED Attempt {retry_count_in_window} (in {window_type_log_msg} window) for {class_name} ({event_id}). Msg: {final_reg_message}")
                                
                                # Common sleep logic for non-fatal attempts before next retry or window expiry check
                                if datetime.now(timezone.utc) + timedelta(seconds=REGISTRATION_RETRY_INTERVAL_WITHIN_WINDOW_SECONDS) < current_loop_attempt_window_end_utc:
                                    logging.info(f"Waiting {REGISTRATION_RETRY_INTERVAL_WITHIN_WINDOW_SECONDS}s before next attempt in {window_type_log_msg} window for {class_name}...")
                                    time.sleep(REGISTRATION_RETRY_INTERVAL_WITHIN_WINDOW_SECONDS)
                                else:
                                    logging.info(f"Not enough time left in {window_type_log_msg} window for another retry for {class_name} ({event_id}). Concluding attempts for this window.")
                                    break # Break if not enough time for sleep and another go
                    # End of retry while loop (window ended, or broke due to success/fatal)
                    
                    # After the while loop, determine final status if not already set by success/fatal
                    if not registration_succeeded_this_event and not event_processed_this_cycle:
                        # This means the window ended, no success, and not a fatal error that already recorded it.
                        
                        logging.debug(f"Post-loop check for {event_id}: final_reg_message='{final_reg_message}' (type: {type(final_reg_message)}), retry_count={retry_count_in_window}")
                        # Check the final_reg_message to see if the API still reported "too soon" as the last reason.
                        if final_reg_message and "registration will be open on" in final_reg_message.lower(): # More robust check
                            logging.info(f"Attempt window ({window_type_log_msg}) for {class_name} ({event_id}) expired. API still reports 'Too Soon'. Message: \"{final_reg_message}\". Will re-evaluate in next cycle.")
                            # DO NOT mark as processed. Let it be re-evaluated in the next main loop iteration.
                            event_processed_this_cycle = False # Explicitly false
                            # Send a specific Discord notification for this scenario
                            if DISCORD_WEBHOOK_URL:
                                embed_payload_still_too_soon = {
                                    "title": f"🟡 Registration Window Expired - API Still Too Soon: {class_name}",
                                    "description": f"The {active_window_duration_for_message}s attempt window ({window_type_log_msg} type) for **{class_name}** (Event ID: {event_id}) has expired.\n**Attempts Made in Window:** {retry_count_in_window}\n**Final API Message:** {final_reg_message}\n\nThe script will re-evaluate this event in the next cycle.",
                                    "color": 0xFFA500, # Orange/Amber
                                    "timestamp": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).isoformat()
                                }
                                if discord_notifier.send_discord_notification(embeds=[embed_payload_still_too_soon], webhook_url=DISCORD_WEBHOOK_URL):
                                    logging.info(f"Sent Discord 'API Still Too Soon After Window' notification for {class_name}.")
                                else:
                                    logging.warning(f"Failed to send Discord 'API Still Too Soon After Window' notification for {class_name}.")
                        else:
                            # The window expired, and the last error was not an explicit "Registration will be open on..."
                            logging.error(f"Registration FAILED for {class_name} ({event_id}) after trying during the active {window_type_log_msg} window (up to {active_window_duration_for_message}s). Final msg: {final_reg_message}")
                            _add_event_to_processed_records(
                                event_id,
                                class_name,
                                activity, # Pass the activity dictionary
                                "FAILURE_WINDOW_EXPIRED",
                                final_reg_message,
                                attempts_in_window=retry_count_in_window
                            )
                            event_processed_this_cycle = True # Mark as processed because window expired with other errors

                            # --- Discord Notification for Failure after Window ---
                            if DISCORD_WEBHOOK_URL:
                                embed_payload_failure = {
                                    "title": f"❌ Registration Failed (Window Expired): {class_name}",
                                    "description": f"Failed to register for **{class_name}** (Event ID: {event_id}) on {activity.get('date')} {activity.get('start_time')} after trying during its {active_window_duration_for_message}s attempt window ({window_type_log_msg} type).\n**Attempts Made in Window:** {retry_count_in_window}\n**Last Error:** {final_reg_message}",
                                    "color": 0xE74C3C, # Red
                                    "timestamp": datetime.now(timezone.utc).astimezone(MOUNTAIN_TZ).isoformat()
                                }
                                if discord_notifier.send_discord_notification(embeds=[embed_payload_failure], webhook_url=DISCORD_WEBHOOK_URL):
                                    logging.info(f"Sent Discord failure (window expired) notification for {class_name}.")
                                else:
                                    logging.warning(f"Failed to send Discord failure (window expired) notification for {class_name}.")
                            # --- End Discord Notification ---
                        
                    if event_processed_this_cycle:
                        # For SUCCESS or FATAL_API_ERROR or FAILURE_WINDOW_EXPIRED (non-too-soon)
                        # _add_event_to_processed_records is called within their respective blocks.
                        pass 
                    # If event_processed_this_cycle is False here, it means it was an API "too soon" situation
                    # throughout the window, and it should be re-attempted in the next main loop cycle.
                    # No record is saved to processed_event_ids.json for this case yet.

                    # ---- MODIFICATION FOR RUN_ONCE_FOR_TESTING ----
                    if RUN_ONCE_FOR_TESTING:
                        logging.info(f"RUN_ONCE_FOR_TESTING: Registration attempt cycle for class '{class_name}' ({event_id}) completed. Halting further class checks in this run.")
                        break # Break from this for loop (iterating through activities)
                    # ---------------------------------------------
                # This else was for: if now_utc_datetime >= registration_opens_datetime_utc:
                # It's no longer needed due to the new window logic handling all cases (before window, in window, after window)
                # else:
                #     reg_opens_dt_mt_str = registration_opens_datetime_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                #     logging.debug(f"  Registration window not yet open for {class_name} ({event_id}). Opens: {reg_opens_dt_mt_str}")

            # --- Check for RUN_ONCE_FOR_TESTING exit condition ---
            if RUN_ONCE_FOR_TESTING:
                # This condition will be met after the schedule fetch attempt (successful or not if it was the first) 
                # and after iterating through activities (potentially breaking early if one registration was triggered).
                if schedule_fetched_this_iteration or (last_schedule_fetch_time != 0 and not schedule_fetched_this_iteration) or (last_schedule_fetch_time == 0) :
                    logging.info("RUN_ONCE_FOR_TESTING: Processing cycle complete. Exiting.")
                    break # Exit the main while True loop

            # --- Dynamic Sleep Logic (replaces the old simple time.sleep) ---
            save_processed_events() # Save state before potentially long sleep

            now_for_sleep_calc = datetime.now(timezone.utc)
            next_event_description = "No specific upcoming events identified."
            target_next_event_time_utc = None
            sleep_seconds_to_perform = DEFAULT_MAX_SLEEP_INTERVAL_S # Default to max sleep

            # 1. Determine the time of the soonest pending registration window
            next_pending_attempt_window_start_utc = None
            if current_schedule_activities:
                for activity_detail_sleep in current_schedule_activities: # Renamed to avoid conflict
                    event_id_sleep = activity_detail_sleep.get("id")
                    if event_id_sleep in processed_event_id_set: # Use renamed set
                        continue
                    try:
                        start_ts_ms_sleep = int(activity_detail_sleep.get("start_timestamp"))
                        event_start_dt_sleep = datetime.fromtimestamp(start_ts_ms_sleep / 1000, timezone.utc)
                        reg_opens_dt_sleep = event_start_dt_sleep - timedelta(minutes=REGISTRATION_OPEN_MINUTES_BEFORE_EVENT)
                        
                        # Calculate start of our defined attempt window
                        attempt_win_start_dt_sleep = reg_opens_dt_sleep - timedelta(seconds=REGISTRATION_ATTEMPT_LEAD_TIME_SECONDS)

                        if attempt_win_start_dt_sleep > now_for_sleep_calc: # Only consider future times
                            if next_pending_attempt_window_start_utc is None or attempt_win_start_dt_sleep < next_pending_attempt_window_start_utc:
                                next_pending_attempt_window_start_utc = attempt_win_start_dt_sleep
                    except (ValueError, TypeError): # Added TypeError
                        pass # Error would have been logged when this activity was first evaluated in the loop

            if next_pending_attempt_window_start_utc:
                target_next_event_time_utc = next_pending_attempt_window_start_utc
                next_attempt_win_start_mt_str = next_pending_attempt_window_start_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                # Calculate and format time until this next registration attempt window starts
                time_delta_to_next_attempt_win = next_pending_attempt_window_start_utc - now_for_sleep_calc
                time_until_next_attempt_win_hr = format_timedelta_to_human_readable(time_delta_to_next_attempt_win)
                next_event_description = f"next registration attempt window opens at {next_attempt_win_start_mt_str} (in {time_until_next_attempt_win_hr})"

            # 2. Determine the time for the next schedule fetch
            # Ensure last_schedule_fetch_time is not 0 before adding SCHEDULE_CHECK_INTERVAL_SECONDS if we want to avoid immediate re-fetch after initial failure.
            # However, if it's 0, next_schedule_fetch_due_utc calculation is fine, it just means it's due "now" or in the past.
            next_schedule_fetch_due_utc = datetime.fromtimestamp(last_schedule_fetch_time + SCHEDULE_CHECK_INTERVAL_SECONDS, timezone.utc)

            if next_schedule_fetch_due_utc > now_for_sleep_calc:
                if target_next_event_time_utc is None or next_schedule_fetch_due_utc < target_next_event_time_utc:
                    target_next_event_time_utc = next_schedule_fetch_due_utc
                    next_fetch_due_mt_str = next_schedule_fetch_due_utc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
                    next_event_description = f"next schedule fetch due at {next_fetch_due_mt_str}"
            # If next_schedule_fetch_due_utc <= now_for_sleep_calc, it means it's time (or past time) to fetch.
            # The main fetch logic at the top of the loop will handle it. A short sleep is appropriate if no closer registration event.

            # 3. Calculate sleep duration based on the identified target_next_event_time_utc
            if target_next_event_time_utc: # If there is a specific future event (registration or schedule fetch)
                delta_seconds = (target_next_event_time_utc - now_for_sleep_calc).total_seconds()
                # Sleep at least MIN_SLEEP_INTERVAL_S, at most DEFAULT_MAX_SLEEP_INTERVAL_S, or until the event
                sleep_seconds_to_perform = max(MIN_SLEEP_INTERVAL_S, min(delta_seconds, DEFAULT_MAX_SLEEP_INTERVAL_S))
            else:
                # No specific *future* target event identified. This means:
                # - All registrations are in the past or processed.
                # - AND Next schedule fetch is also in the past (or it's the very first run and last_schedule_fetch_time is 0).
                if last_schedule_fetch_time == 0 and not schedule_fetched_this_iteration:
                    # Initial login/fetch failed or yielded nothing, and it's the first attempt cycle for fetching.
                    sleep_seconds_to_perform = INITIAL_FETCH_RETRY_INTERVAL_S
                    next_event_description = f"initial login/schedule fetch was not successful. Retrying tasks in {INITIAL_FETCH_RETRY_INTERVAL_S}s"
                else:
                    # All pending events (regs/fetch) are in the past or current moment.
                    # The loop will immediately re-evaluate them. So, just MIN_SLEEP_INTERVAL_S.
                    sleep_seconds_to_perform = MIN_SLEEP_INTERVAL_S
                    if not next_event_description or next_event_description == "No specific upcoming events identified.":
                         if next_schedule_fetch_due_utc <= now_for_sleep_calc:
                            next_event_description = "next schedule fetch is due now or was due"
                         else: # Should not happen if target_next_event_time_utc is None
                            next_event_description = "evaluating immediate tasks"
           
            # Final log before sleeping
            current_time_log_mt_str = now_for_sleep_calc.astimezone(MOUNTAIN_TZ).strftime('%Y-%m-%d %I:%M %p %Z')
            logging.info(f"Current time: {current_time_log_mt_str}. {next_event_description.capitalize()}. Sleeping for {sleep_seconds_to_perform:.1f} seconds.")
            time.sleep(sleep_seconds_to_perform)

    except KeyboardInterrupt:
        logging.info("Script stopped by user.")
    except Exception as e: # Catch any other unexpected exceptions in the main loop
        logging.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        save_processed_events() # Ensure state is saved on exit
        logging.info("Exiting Lifetime Auto-Scheduler.")

if __name__ == "__main__":
    main() 
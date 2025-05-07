import requests
import json
from datetime import datetime, date, timedelta, timezone
import logging
from dotenv import load_dotenv

# Assuming lifetime_auth.py is in the same directory or accessible
from lifetime_auth import perform_login

# --- Configuration Constants ---
# Class name filters - Now lists of strings
INCLUDE_IN_CLASS_NAME = ["intermediate"] # e.g., ["intermediate", "open play"]
EXCLUDE_FROM_CLASS_NAME = ["advanced", "singles"]   # e.g., ["advanced", "beginner", "league"]

# Day/Time filters
WEEKEND_DAYS = ["saturday", "sunday"]
ALLOWED_WEEKDAY_DAY_PARTS = ["Evening"] # Activities on weekdays must be in one of these day parts.
# For weekends, all day parts that pass other filters are implicitly allowed.

# Date range for API query
DAYS_FROM_NOW_FOR_START_DATE = 7   # Offset from current date for the start of the period. 0 means today.
FETCH_DURATION_DAYS = 10           # Number of days to fetch data for, including the start date.

def fetch_lifetime_data(jwe_token: str, ssoid_token: str):
    """
    Fetches schedule data from the Lifetime Fitness API using provided auth tokens.
    Args:
        jwe_token (str): The x-ltf-jwe authentication token.
        ssoid_token (str): The x-ltf-ssoid authentication token.
    """
    today = date.today()
    start_date_obj = today + timedelta(days=DAYS_FROM_NOW_FOR_START_DATE)
    end_date_obj = start_date_obj + timedelta(days=FETCH_DURATION_DAYS - 1)

    start_month_str = str(start_date_obj.month)
    start_day_str = f"{start_date_obj.day:02d}"
    start_year_str = str(start_date_obj.year)
    start_date_api_format = f"{start_month_str}%2F{start_day_str}%2F{start_year_str}"

    end_month_str = str(end_date_obj.month)
    end_day_str = f"{end_date_obj.day:02d}"
    end_year_str = str(end_date_obj.year)
    end_date_api_format = f"{end_month_str}%2F{end_day_str}%2F{end_year_str}"

    base_url = 'https://api.lifetimefitness.com/ux/web-schedules/v2/schedules/classes'
    params = f"start={start_date_api_format}&end={end_date_api_format}&tags=interest%3APickleball%20Open%20Play&tags=format%3AClass&locations=Denver%20West&isFree=false&facet=tags%3Ainterest%2Ctags%3AdepartmentDescription%2Ctags%3AtimeOfDay%2Ctags%3Aage%2Ctags%3AskillLevel%2Ctags%3Aintensity%2Cleader.name.displayname%2Clocation.name&page=1&pageSize=750"
    url = f"{base_url}?{params}"
    print(f"Fetching data from URL: {url}")
    
    # Generate dynamic timestamp
    dynamic_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.7',
        'cache-control': 'no-cache',
        'ocp-apim-subscription-key': '924c03ce573d473793e184219a6a19bd',
        'origin': 'https://my.lifetime.life',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://my.lifetime.life/',
        'sec-ch-ua': '"Brave";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'x-ltf-jwe': jwe_token, # Use passed JWE token
        'x-ltf-ssoid': ssoid_token, # Use passed SSOID token
        'x-timestamp': dynamic_timestamp # Use dynamically generated timestamp
        # Removed static x-ltf-profile as it should ideally be linked with JWE generation
    }
    
    if not jwe_token or not ssoid_token:
        print("Error in fetch_lifetime_data: JWE or SSOID token is missing.")
        return None

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An error occurred during the request: {req_err}")
    except json.JSONDecodeError:
        print("Failed to decode JSON from response.")
        print(f"Response content: {response.text}")
    return None

def process_and_filter_data(data):
    """
    Processes API data, filters activities based on list criteria, and returns a list of activity dictionaries.
    """
    processed_activities = []
    if not data or "results" not in data:
        # Use logging if available, otherwise print
        try: logging.warning("No results found in the data to process.")
        except NameError: print("No results found in the data to process.")
        return processed_activities

    for day_info in data.get("results", []):
        current_date_str = day_info.get("day")
        try:
            current_date_obj = datetime.strptime(current_date_str, "%Y-%m-%d")
            day_of_week = current_date_obj.strftime("%A")
        except (ValueError, TypeError):
            day_of_week = "N/A"

        for day_part in day_info.get("dayParts", []):
            day_part_name = day_part.get("name")
            for start_time_info in day_part.get("startTimes", []):
                start_time_str = start_time_info.get("time")
                start_timestamp = start_time_info.get("timestamp")
                for activity in start_time_info.get("activities", []):
                    activity_name = activity.get("name", "")
                    activity_name_lower = activity_name.lower()
                    
                    # --- Updated Class Name Filtering Logic ---
                    # Check for inclusion (must contain at least one term)
                    include_match = False
                    if not INCLUDE_IN_CLASS_NAME: # If include list is empty, always pass this check
                        include_match = True
                    else:
                        for term in INCLUDE_IN_CLASS_NAME:
                            if term.lower() in activity_name_lower:
                                include_match = True
                                break # Found one match, no need to check further include terms
                    
                    if not include_match:
                        continue # Skip if no include term matched
                    
                    # Check for exclusion (must not contain any term)
                    exclude_match = False
                    if EXCLUDE_FROM_CLASS_NAME: # Only check if exclude list is not empty
                        for term in EXCLUDE_FROM_CLASS_NAME:
                            if term.lower() in activity_name_lower:
                                exclude_match = True
                                break # Found one match, no need to check further exclude terms
                    
                    if exclude_match:
                        continue # Skip if any exclude term matched
                    # --- End Updated Filtering Logic ---

                    # Apply day part filter (logic remains the same)
                    passes_day_part_filter = False
                    if day_of_week != "N/A" and day_of_week.lower() in WEEKEND_DAYS:
                        passes_day_part_filter = True 
                    elif day_part_name in ALLOWED_WEEKDAY_DAY_PARTS:
                        passes_day_part_filter = True
                    
                    if passes_day_part_filter:
                        # --- NEW: isPaidClass Filter ---
                        is_paid = activity.get("isPaidClass", False) # Default to False if key missing
                        if is_paid is True: # Explicitly check for True
                            continue # Skip paid classes
                        # --- End isPaidClass Filter ---
                        
                        # Add activity if all filters passed
                        processed_activities.append({
                            "id": activity.get("id"),
                            "class_name": activity_name,
                            "date": current_date_str,
                            "day_of_week": day_of_week,
                            "day_part": day_part_name,
                            "start_time": start_time_str,
                            "start_timestamp": start_timestamp,
                            "end_time": activity.get("endTime"),
                            "end_timestamp": activity.get("endTimestamp"),
                            "duration": activity.get("duration"),
                            "cta": activity.get("cta"),
                            "isPaidClass": is_paid, # Include the value we checked
                            "isRegisterable": activity.get("isRegistrable"),
                            "location": activity.get("location")
                        })
    return processed_activities

def write_to_json(activities, filename="lifetime_schedule_filtered.json"):
    """
    Writes a list of activity dictionaries to a JSON file.
    """
    if not activities:
        print("No activities found to write to JSON.")
        return False

    try:
        with open(filename, "w", encoding="utf-8") as jsonfile:
            json.dump(activities, jsonfile, indent=4)
        print(f"\\nData successfully written to {filename}")
        return True
    except IOError:
        print(f"Error writing to file {filename}.")
        return False
    except TypeError as e:
        print(f"Error serializing data to JSON: {e}")
        return False

def get_filtered_schedule(jwe_token: str, ssoid_token: str):
    """
    Fetches, processes, and filters Lifetime Fitness schedule data using provided auth tokens.
    Returns a list of filtered activities or None if an error occurs.
    Args:
        jwe_token (str): The x-ltf-jwe authentication token.
        ssoid_token (str): The x-ltf-ssoid authentication token.
    """
    if not jwe_token or not ssoid_token:
        print("Error in get_filtered_schedule: JWE or SSOID token is missing.")
        return None

    print("Fetching Lifetime Fitness data with auth tokens...")
    api_data = fetch_lifetime_data(jwe_token, ssoid_token)
    
    if api_data:
        print("Data fetched successfully. Processing and filtering activities...")
        filtered_activities = process_and_filter_data(api_data)
        if filtered_activities:
            print(f"Found {len(filtered_activities)} activities matching the criteria.")
            return filtered_activities
        else:
            print("No activities matched the filtering criteria.")
            return [] 
    else:
        print("Failed to fetch data or data was empty.")
        return None 

def fetch_and_save_schedule(output_filename: str, jwe_token: str, ssoid_token: str):
    """
    Fetches the filtered schedule and saves it directly to a JSON file.

    Args:
        output_filename (str): The path to the JSON file to save results.
        jwe_token (str): The x-ltf-jwe authentication token.
        ssoid_token (str): The x-ltf-ssoid authentication token.

    Returns:
        bool: True if the schedule was fetched and saved successfully, False otherwise.
    """
    logging.info(f"Attempting to fetch schedule and save to {output_filename}...")
    schedule = get_filtered_schedule(jwe_token, ssoid_token)
    
    if schedule is not None: # Check if fetching succeeded (didn't return None)
        logging.info(f"Fetch successful. Found {len(schedule)} activities. Saving...")
        if write_to_json(schedule, output_filename):
            logging.info(f"Schedule successfully saved to {output_filename}")
            return True
        else:
            logging.error(f"Failed to write schedule to {output_filename}")
            return False
    else: # Fetching failed
        logging.error("Schedule fetching failed. Cannot save to file.")
        return False

if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    # Load .env file for credentials needed by perform_login
    load_dotenv()

    logging.info("Running schedule_fetcher.py standalone to fetch and save schedule...")
    
    output_file = "schedule_output.json"
    
    # --- Get Live Auth Tokens --- 
    logging.info("Attempting login via lifetime_auth.perform_login()...")
    jwe_token, ssoid_token = perform_login()
    # -----------------------------

    if not jwe_token or not ssoid_token:
        logging.error("Login failed. Cannot fetch schedule. Ensure .env file is correct and lifetime_auth.py is functional.")
    else:
        logging.info(f"Login successful. Tokens received. Proceeding to fetch and save schedule to {output_file}.")
        success = fetch_and_save_schedule(output_file, jwe_token, ssoid_token)
        if success:
            logging.info("Standalone run finished successfully.")
        else:
            logging.error("Standalone run finished with errors (fetch or save failed).")

"""N.B. The JWE and Profile tokens are also static and will expire; these need to be handled by an auth module.
For this refactoring step, we are focusing on the structure, not fixing auth token issues yet.
The original generate_lifetime_table.py did not have a shebang, adding one.
""" 
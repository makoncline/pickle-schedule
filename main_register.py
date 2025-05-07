import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Import functions from our new modules
from lifetime_auth import perform_login
from lifetime_registration import initiate_registration, complete_registration

# --- Load Environment Variables ---
load_dotenv() # Load variables from .env file into environment

# --- Configuration ---
EVENT_ID_TO_REGISTER = "ZXhlcnA6MzMyYm9vazM1NTg2NjoyMDI1LTA1LTA4"  # Replace with the target eventId
MEMBER_IDS_TO_REGISTER = [115608390]  # Replace with the target memberId(s), e.g., [115608390, 115608391]

# Base headers common to registration requests (excluding JWE, SSOID, Timestamp, Content-Type)
# Content-Type will be added by the helper
BASE_COMMON_HEADERS = {
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
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
}

def get_request_headers(jwe_token, ssoid_token):
    """Helper function to construct headers for registration requests."""
    if not jwe_token or not ssoid_token:
        print("Critical Error: JWE or SSOID token is missing. Cannot construct headers.")
        return None
        
    headers = BASE_COMMON_HEADERS.copy()
    headers['content-type'] = 'application/json' # For POST/PUT with JSON body
    headers['x-ltf-jwe'] = jwe_token
    headers['x-ltf-ssoid'] = ssoid_token
    headers['x-timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    # Explicitly NOT adding x-ltf-profile based on previous test results
    return headers

if __name__ == "__main__":
    print("Starting registration process...")

    # 1. Perform Login
    jwe, ssoid = perform_login()
    if not jwe or not ssoid:
        print("Login failed. Exiting.")
        exit()
    print("Login successful. Proceeding with registration attempts...")

    # 2. Check Configurations
    if not EVENT_ID_TO_REGISTER:
        print("Error: EVENT_ID_TO_REGISTER is not set. Please configure it.")
        exit()
    if not MEMBER_IDS_TO_REGISTER:
        print("Error: MEMBER_IDS_TO_REGISTER is empty. Please configure it.")
        exit()

    # 3. Attempt registration for the configured members and event
    print(f"\n======= Processing Members {MEMBER_IDS_TO_REGISTER} for Event {EVENT_ID_TO_REGISTER} ======")
        
    # Get headers for Step 1
    step1_headers = get_request_headers(jwe, ssoid)
    if not step1_headers:
        print(f"Failed to construct headers for Step 1. Aborting.")
        exit() 

    # Execute Step 1: Initiate Registration
    # Pass the entire list of member IDs
    step1_result = initiate_registration(EVENT_ID_TO_REGISTER, MEMBER_IDS_TO_REGISTER, step1_headers)
        
    # Extract results from Step 1
    reg_id = step1_result.get("regId")
    agreement_id = step1_result.get("agreementId")
    step1_response_data = step1_result.get("response", {})
    step1_error = step1_result.get("error")
    is_fatal = step1_response_data.get("validation", {}).get("isFatal", False) if isinstance(step1_response_data, dict) else False
    notification = step1_response_data.get("validation", {}).get("notification") if isinstance(step1_response_data, dict) else None

    # Check if Step 1 allows proceeding to Step 2
    if reg_id and agreement_id and not is_fatal:
        print(f"Step 1 successful for members {MEMBER_IDS_TO_REGISTER} (Reg ID: {reg_id}). Proceeding to Step 2.")
            
        # Get headers for Step 2 (regenerate for fresh timestamp)
        step2_headers = get_request_headers(jwe, ssoid)
        if not step2_headers:
             print(f"Failed to construct headers for Step 2. Skipping completion.")
             exit() # Exit if headers fail for group

        # Execute Step 2: Complete Registration
        # Pass the entire list of member IDs
        step2_success, step2_status, step2_response = complete_registration(reg_id, MEMBER_IDS_TO_REGISTER, agreement_id, step2_headers)
            
        if step2_success:
            print(f"Registration COMPLETED successfully for members {MEMBER_IDS_TO_REGISTER}.")
        else:
            print(f"Step 2 FAILED for members {MEMBER_IDS_TO_REGISTER}. Status: {step2_status}, Response: {step2_response}")
        
    else:
        print(f"Step 1 FAILED or conditions not met for Step 2 for members {MEMBER_IDS_TO_REGISTER}.")
        if is_fatal:
            print(f"  Reason: Fatal validation error indicated by API. Notification: {notification}")
        elif step1_error:
            print(f"  Reason: {step1_error}")
        elif not reg_id:
             print("  Reason: Missing registration ID from Step 1 response.")
        elif not agreement_id:
             print("  Reason: Missing agreement ID from Step 1 response (might be okay if no waiver needed, but check API response). ")
        else:
             print("  Reason: Unknown Step 1 failure (check Step 1 Response JSON). ")

    print("\nRegistration process finished.") 
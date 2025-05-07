#!/usr/bin/env python3

import json
from datetime import datetime, timezone

# Assuming lifetime_registration.py exists in the same directory or is in PYTHONPATH
# and provides initiate_registration and complete_registration functions.
# from lifetime_registration import initiate_registration, complete_registration

# Base headers common to registration requests (excluding JWE, SSOID, Timestamp, Content-Type)
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
    
    return headers

def attempt_event_registration(event_id, member_ids, jwe_token, ssoid_token, lifetime_registration_module):
    """
    Attempts to register the given member_ids for the specified event_id.

    Args:
        event_id (str): The ID of the event to register for.
        member_ids (list[int]): A list of member IDs to register.
        jwe_token (str): The JWE authentication token.
        ssoid_token (str): The SSOID authentication token.
        lifetime_registration_module: The imported lifetime_registration module.

    Returns:
        tuple: (success_flag (bool), message (str), response_data (dict or None))
               success_flag is True if registration completed successfully.
               message provides a human-readable status.
               response_data contains the final API response or relevant error info.
    """
    print(f"\nAttempting registration for Event ID: {event_id} with Members: {member_ids}")

    # Get headers for Step 1
    step1_headers = get_request_headers(jwe_token, ssoid_token)
    if not step1_headers:
        return False, "Failed to construct headers for Step 1 (Initiate Registration).", None

    # Execute Step 1: Initiate Registration
    try:
        step1_result = lifetime_registration_module.initiate_registration(event_id, member_ids, step1_headers)
    except Exception as e:
        return False, f"Error during Step 1 (Initiate Registration): {str(e)}", None
        
    reg_id = step1_result.get("regId")
    agreement_id = step1_result.get("agreementId")
    step1_response_data = step1_result.get("response", {})
    step1_error = step1_result.get("error")
    is_fatal = step1_response_data.get("validation", {}).get("isFatal", False) if isinstance(step1_response_data, dict) else False
    notification = step1_response_data.get("validation", {}).get("notification") if isinstance(step1_response_data, dict) else None

    if not (reg_id and agreement_id and not is_fatal):
        message = f"Step 1 (Initiate Registration) FAILED or conditions not met for Step 2."
        if is_fatal:
            message += f" Reason: Fatal validation error. Notification: {notification}"
        elif step1_error:
            message += f" Reason: {step1_error}"
        elif not reg_id:
             message += " Reason: Missing registration ID from Step 1 response."
        elif not agreement_id:
             # This might not always be fatal if no waiver is needed, but the original script implied it was important.
             message += " Reason: Missing agreement ID from Step 1 response."
        else:
             message += " Reason: Unknown Step 1 failure."
        return False, message, step1_response_data

    print(f"Step 1 successful (Reg ID: {reg_id}). Proceeding to Step 2.")
            
    # Get headers for Step 2 (regenerate for fresh timestamp)
    step2_headers = get_request_headers(jwe_token, ssoid_token)
    if not step2_headers:
        return False, "Failed to construct headers for Step 2 (Complete Registration).", None

    # Execute Step 2: Complete Registration
    try:
        step2_success, step2_status, step2_response = lifetime_registration_module.complete_registration(
            reg_id, member_ids, agreement_id, step2_headers
        )
    except Exception as e:
        return False, f"Error during Step 2 (Complete Registration): {str(e)}", None
            
    if step2_success:
        msg = f"Registration COMPLETED successfully for Event ID: {event_id}, Members: {member_ids}."
        print(msg)
        return True, msg, step2_response
    else:
        msg = f"Step 2 (Complete Registration) FAILED for Event ID: {event_id}. Status: {step2_status}"
        print(msg)
        return False, msg, step2_response

# Example of how this might be tested if lifetime_registration was available
# and we had live tokens and a valid event ID.
if __name__ == "__main__":
    print("Testing registration_handler.py (requires dummy lifetime_registration module and inputs)")

    # --- Mocking lifetime_registration for standalone testing --- 
    class MockLifetimeRegistration:
        def initiate_registration(self, event_id, member_ids, headers):
            print(f"MOCK: Initiating registration for {event_id}, members {member_ids}")
            # Simulate a successful initiation that requires a waiver/agreement
            return {
                "regId": "mockReg123", 
                "agreementId": "mockAgree456", 
                "response": {"validation": {"isFatal": False, "notification": "Almost there!"}},
                "error": None
            }
            # Simulate a failure (e.g. event full, already registered)
            # return {"regId": None, "agreementId": None, "response": {"validation": {"isFatal": True, "notification": "Event is full."}}, "error": "EventFull"}

        def complete_registration(self, reg_id, member_ids, agreement_id, headers):
            print(f"MOCK: Completing registration for {reg_id}, agreement {agreement_id}")
            # Simulate successful completion
            return True, 200, {"status": "COMPLETED", "confirmationId": "conf789"}
            # Simulate failure
            # return False, 400, {"status": "FAILED", "message": "Some completion error"}

    mock_lifetime_reg_module = MockLifetimeRegistration()
    # -- End Mocking --

    # Dummy data for testing - REPLACE with real data for actual use
    test_event_id = "ZXhlcnA6MzMyYm9vazM1NTg2NjoyMDI1LTA1LTA4" # From your main_register.py
    test_member_ids = [115608390]  # From your main_register.py
    # These tokens would come from your auth_handler.perform_login()
    test_jwe = "dummy_jwe_token_for_testing"
    test_ssoid = "dummy_ssoid_token_for_testing"

    if not test_jwe or not test_ssoid:
        print("Please provide dummy JWE and SSOID tokens for testing this module.")
    else:
        success, message, data = attempt_event_registration(
            test_event_id, 
            test_member_ids, 
            test_jwe, 
            test_ssoid,
            mock_lifetime_reg_module # Pass the mock module here
        )

        print(f"\n--- Test Result ---")
        print(f"Success: {success}")
        print(f"Message: {message}")
        if data:
            print(f"Response Data: {json.dumps(data, indent=2)}")
        print("---------------------") 
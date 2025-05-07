import requests
import json

# --- API Endpoint ---
BASE_URL_REGISTRATION = "https://api.lifetimefitness.com/sys/registrations/V3/ux"

def initiate_registration(event_id, member_ids, headers):
    """
    Initiates the registration process (Step 1).
    Args:
        event_id (str): The specific event ID to register for.
        member_ids (list[int]): The list of member IDs to register.
        headers (dict): The required request headers (including JWE, SSOID, Timestamp).
    Returns:
        dict: A dictionary containing 'regId', 'agreementId', 'response', and potentially 'error'.
              'regId' and 'agreementId' will be None on failure or if not found.
              'response' contains the full JSON response or error text.
              'error' contains a string message on specific failures.
    """
    initial_url = f"{BASE_URL_REGISTRATION}/event"
    initial_payload = {
        "eventId": event_id,
        "memberId": member_ids  # Use the list directly
    }

    print(f"\nStep 1: Initiating registration for Members {member_ids}...")
    print(f"URL: POST {initial_url}")
    # print(f"Headers: {json.dumps(headers, indent=2)}") # Uncomment for deep debugging
    print(f"Payload: {json.dumps(initial_payload)}")

    result = {"regId": None, "agreementId": None, "response": None, "error": None}

    try:
        response = requests.post(initial_url, headers=headers, json=initial_payload, timeout=30)
        print(f"Step 1 Response Status Code: {response.status_code}")

        try:
            response_json = response.json()
            print(f"Step 1 Response JSON:\n{json.dumps(response_json, indent=2)}")
            result["response"] = response_json

            if response.status_code // 100 == 2: # Check for 2xx success
                result["regId"] = response_json.get("regId")
                agreement_info = response_json.get("agreement", {})
                result["agreementId"] = agreement_info.get("agreementId")

                if not result["regId"]:
                    print("Error: 'regId' not found in Step 1 response.")
                    result["error"] = "Missing regId"
                if not result["agreementId"]:
                    # This might be okay if no agreement needed, but flag it
                    print("Warning: 'agreement.agreementId' not found in Step 1 response.")
                    # result["error"] = "Missing agreementId" # Decide if this is truly an error

            else:
                print(f"Step 1 failed with status code {response.status_code}.")
                result["error"] = f"Step 1 HTTP Error: {response.status_code}"

        except json.JSONDecodeError:
            print(f"Step 1 Response Content (not JSON):\n{response.text}")
            result["response"] = response.text
            result["error"] = "Non-JSON response"

    except requests.exceptions.RequestException as e:
        print(f"Step 1 Request Exception: {e}")
        result["error"] = f"Request Exception: {e}"

    return result

def complete_registration(reg_id, member_ids, agreement_id, headers):
    """
    Completes the registration process (Step 2).
    Args:
        reg_id (int): The registration ID obtained from Step 1.
        member_ids (list[int]): The list of member IDs being registered.
        agreement_id (str): The agreement ID obtained from Step 1 (needs to be int for payload).
        headers (dict): The required request headers (including JWE, SSOID, Timestamp).
    Returns:
        tuple: (success_bool, status_code, response_text_or_json)
    """
    complete_url = f"{BASE_URL_REGISTRATION}/event/{reg_id}/complete"
    complete_payload = {
        "memberId": member_ids,  # Use the list directly
        "acceptedDocuments": [int(agreement_id)] # Ensure agreement_id is an int
    }

    print(f"\nStep 2: Completing registration for Members {member_ids} (Reg ID: {reg_id})...")
    print(f"URL: PUT {complete_url}")
    # print(f"Headers: {json.dumps(headers, indent=2)}") # Uncomment for deep debugging
    print(f"Payload: {json.dumps(complete_payload)}")

    success = False
    status_code = None
    response_output = None

    try:
        response = requests.put(complete_url, headers=headers, json=complete_payload, timeout=30)
        status_code = response.status_code
        print(f"Step 2 Response Status Code: {status_code}")

        if response.text:
            try:
                response_output = response.json()
                print(f"Step 2 Response JSON:\n{json.dumps(response_output, indent=2)}")
            except json.JSONDecodeError:
                response_output = response.text
                print(f"Step 2 Response Content (not JSON):\n{response_output}")
        else:
             print("Step 2 Response: No body content.")
             response_output = "(No content)"

        if status_code // 100 == 2:
            print(f"Successfully completed registration for Members {member_ids} (Reg ID: {reg_id})")
            success = True
        else:
            print(f"Step 2 failed with status code {status_code}.")

    except requests.exceptions.RequestException as e:
        print(f"Step 2 Request Exception: {e}")
        response_output = f"Request Exception: {e}"

    return success, status_code, response_output 
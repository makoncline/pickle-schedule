import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Endpoint ---
LOGIN_URL = "https://api.lifetimefitness.com/auth/v2/login"

# --- Headers ---
# Headers specific to the login request
LOGIN_HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'no-cache',
    'content-type': 'application/json; charset=UTF-8',
    'ocp-apim-subscription-key': '924c03ce573d473793e184219a6a19bd',
    'ocp-apim-trace': 'true',
    'origin': 'https://my.lifetime.life',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
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

def perform_login():
    """
    Performs login using credentials from .env file.
    Returns:
        tuple: (jwe_token, ssoid_token) on success, (None, None) on failure.
    """
    LIFETIME_USERNAME = os.getenv("LIFETIME_USERNAME")
    LIFETIME_PASSWORD = os.getenv("LIFETIME_PASSWORD")

    if not LIFETIME_USERNAME or not LIFETIME_PASSWORD:
        print("Error: LIFETIME_USERNAME or LIFETIME_PASSWORD not found in environment variables.")
        print("Please ensure they are set in your .env file.")
        return None, None

    print("\nAttempting login...")
    login_payload = {
        "username": LIFETIME_USERNAME,
        "password": LIFETIME_PASSWORD
    }

    jwe_token = None
    ssoid_token = None

    try:
        response = requests.post(LOGIN_URL, headers=LOGIN_HEADERS, json=login_payload, timeout=30)
        print(f"Login Response Status Code: {response.status_code}")

        if response.status_code // 100 == 2: # Successful login (2xx)
            print("Login successful!")
            try:
                response_data = response.json()
                print(f"Login Response JSON:\n{json.dumps(response_data, indent=2)}")

                jwe_token = response_data.get('token') # Directly from observed response structure
                ssoid_token = response_data.get('ssoId') # Directly from observed response structure

                print(f"  Extracted JWE (token) from body: {jwe_token is not None}")
                print(f"  Extracted ssoId from body: {ssoid_token is not None}")

                if not jwe_token or not ssoid_token:
                     print("Error: Failed to extract JWE token or SSOID from login response body.")
                     return None, None # Critical failure

            except json.JSONDecodeError:
                print("Login response was not JSON. Cannot extract tokens from body.")
                return None, None # Critical failure
        else:
            print(f"Login failed. Response Text:\n{response.text}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"Login Request Exception: {e}")
        return None, None

    return jwe_token, ssoid_token

if __name__ == '__main__':
    # Example usage if running this file directly
    print("Testing login function...")
    jwe, ssoid = perform_login()
    if jwe and ssoid:
        print("\nLogin Test Successful:")
        print(f"  JWE Token obtained: {jwe[:20]}...") # Print beginning of token
        print(f"  SSOID obtained: {ssoid}")
    else:
        print("\nLogin Test Failed.") 
# Lifetime Class Auto-Registration Project: Plan and Progress

This document outlines the plan and tracks the progress for creating an automated system to register for Lifetime Fitness classes.

## Phase 1: Refactor Existing Scripts into Reusable Modules

- [x] **Step 1: `schedule_fetcher.py` (Refactoring `generate_lifetime_table.py`)**

  - [x] Modify `generate_lifetime_table.py` (or create `schedule_fetcher.py`).
  - [x] Ensure `fetch_lifetime_data()` is reusable.
  - [x] Ensure `process_and_filter_data(data)` returns `processed_activities`.
  - [x] Create a primary function, e.g., `get_filtered_schedule()`, that combines fetching and filtering.
  - [x] Keep/manage configuration constants.
  - [x] Keep `if __name__ == "__main__":` for independent testing.

- [x] **Step 2: `auth_handler.py` (Utilizing existing `lifetime_auth.py`)**

  - [x] Verify `lifetime_auth.py` exists and provides `perform_login()` returning `jwe` and `ssoid`.
  - [x] Ensure it handles credentials securely (e.g., from env vars).
  - [x] _No direct coding changes anticipated here if `lifetime_auth.py` is already functional._

- [x] **Step 3: `registration_handler.py` (Refactoring `main_register.py` and using `lifetime_registration.py`)**

  - [x] Create a new file named `registration_handler.py`.
  - [x] Assume `lifetime_registration.py` (with `initiate_registration`, `complete_registration`) exists.
  - [x] Move `BASE_COMMON_HEADERS` and `get_request_headers` from `main_register.py` to `registration_handler.py`.
  - [x] Create a primary function `attempt_event_registration(event_id, member_ids, jwe_token, ssoid_token)`.
  - [x] This function will orchestrate registration steps and return success/failure.

- [x] **Step 4: `notification_sender.py` (Refactoring `lifetime_class_checker.py`)**
  - [x] Create a new file named `notification_sender.py`.
  - [x] Move `send_text_via_email` from `lifetime_class_checker.py` to `notification_sender.py`.
  - [x] Modify the function to accept message and configurations as parameters.

## Phase 2: Create the Main Orchestrator (`auto_scheduler_main.py`)

- [x] **Step 5: `auto_scheduler_main.py` - Initial Setup and Configuration**

  - [x] Create `auto_scheduler_main.py`.
  - [x] Import functions from Phase 1 modules.
  - [x] Define/load all configurations (credentials, member IDs, filter criteria, notification settings, timing constants).

- [x] **Step 6: `auto_scheduler_main.py` - Main Loop and State Management**

  - [x] Initialize `processed_event_ids` set (consider persistence).
  - [x] Implement main `while True:` loop.
  - [x] Manage timing for daily schedule fetches and frequent registration checks.

- [x] **Step 7: `auto_scheduler_main.py` - Fetching Schedule (Daily)**

  - [x] Track `last_schedule_fetch_time`.
  - [x] Periodically call `schedule_fetcher.get_filtered_schedule()`.
  - [x] Store `filtered_activities`.
  - [x] Update `last_schedule_fetch_time`.
  - [x] Log activity.

- [x] **Step 8: `auto_scheduler_main.py` - Authentication (As Needed)**

  - [x] Ensure valid `jwe` and `ssoid` tokens before registration attempts.
  - [x] Call `auth_handler.perform_login()`.
  - [x] Handle login failures.

- [x] **Step 9: `auto_scheduler_main.py` - Registration Logic (Frequent Checks)**
  - [x] Loop runs frequently.
  - [x] Iterate through `filtered_activities`.
  - [x] Skip if event ID in `processed_event_ids`.
  - [x] Parse `start_timestamp`, calculate `registration_opening_time`.
  - [x] Compare with current UTC time.
  - [x] If window open:
    - [x] Call `registration_handler.attempt_event_registration()`.
    - [x] On success: log, construct message, call `notification_sender.send_sms_notification()`, add to `processed_event_ids`.
    - [x] On failure: log, add to `processed_event_ids` (consider retries).
  - [x] Sleep for `REGISTRATION_ATTEMPT_CHECK_INTERVAL_MINUTES`.

## Phase 3: Refinements, Error Handling, and Logging

- [x] **Step 10: Robust Error Handling and Logging**

  - [x] Implement `try-except` blocks extensively. (Reviewed and enhanced in main loop)
  - [x] Use Python's `logging` module. (Implemented in auto_scheduler_main.py)

- [x] **Step 11: Timestamp and Timezone Consistency**

  - [x] Verify all timestamp handling is UTC-aware. (Confirmed as implemented)

- [~] **Step 12: Configuration Management**

  - [x] Ensure sensitive data/parameters are loaded from `.env` or config files. (Implemented via `load_dotenv()`)

- [ ] **Step 13: State Persistence for `processed_event_ids`**

  - [ ] Save and load `processed_event_ids` to/from a file.

- [ ] **Step 14: Graceful Shutdown**
  - [ ] Handle `KeyboardInterrupt` for clean exits.

---

_This document will be updated as tasks are completed._

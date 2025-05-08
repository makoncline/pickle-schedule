#!/bin/bash

# Script to update and restart the Lifetime Auto-Scheduler bot
# This script is intended to be run on the server (e.g., Raspberry Pi)

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Adjust these paths if your setup on the server is different.
# Make sure PROJECT_DIR is the absolute path to your project on the server.
PROJECT_DIR="/root/pickle-schedule" # Path on the Raspberry Pi
SERVICE_NAME="lifetime-scheduler.service" # systemd service name on the Pi
GIT_REMOTE="origin" # Your git remote name
GIT_BRANCH="main"   # The branch you want to pull from
# --- End Configuration ---

VENV_PATH="$PROJECT_DIR/.venv/bin/activate"

echo "=== Starting Lifetime Auto-Scheduler Update (on server) ==="

echo "INFO: Navigating to project directory: $PROJECT_DIR"
cd "$PROJECT_DIR" || { echo "ERROR: Failed to navigate to project directory '$PROJECT_DIR'. Exiting."; exit 1; }

echo "INFO: Current directory: $(pwd)"

echo "INFO: Pulling latest changes from Git (Remote: $GIT_REMOTE, Branch: $GIT_BRANCH)..."
git pull "$GIT_REMOTE" "$GIT_BRANCH"

echo "INFO: Activating virtual environment..."
source "$VENV_PATH" || { echo "ERROR: Failed to activate virtual environment at '$VENV_PATH'. Exiting."; exit 1; }

echo "INFO: Installing/updating Python dependencies from requirements.txt..."
pip install -r requirements.txt

echo "INFO: Deactivating virtual environment..."
deactivate

echo "INFO: Restarting $SERVICE_NAME systemd service..."
# This command requires sudo privileges on the server
sudo systemctl restart "$SERVICE_NAME"

echo "INFO: Update complete."
echo "--------------------------------------------------"
echo "INFO: Current status of $SERVICE_NAME:"
# This command requires sudo privileges on the server
sudo systemctl status "$SERVICE_NAME" --no-pager
echo "--------------------------------------------------"

echo "INFO: To monitor logs (on server), you can use:"
echo "      sudo journalctl -u $SERVICE_NAME -f"
echo "      sudo tail -n 50 /var/log/lifetime-scheduler.log" # Path on the server
echo "      sudo tail -n 50 /var/log/lifetime-scheduler.err" # Path on the server
echo "=== Lifetime Auto-Scheduler Update Finished ==="

exit 0 
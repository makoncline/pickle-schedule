.PHONY: logs start stop restart status clean update help

# This Makefile is intended for interacting with the systemd service on the Raspberry Pi.

SERVICE_NAME := lifetime-scheduler.service
SERVICE_LOG_FILE := /var/log/lifetime-scheduler.log
SERVICE_ERR_FILE := /var/log/lifetime-scheduler.err
UPDATE_SCRIPT := ./update_scheduler.sh

logs:
	@echo "Showing last 100 lines of systemd service log ($(SERVICE_LOG_FILE)) and tailing..."
	@echo "Note: You might need to run 'sudo make logs' if your user doesn't have permission to read this file directly."
	@tail -n 100 -f $(SERVICE_LOG_FILE)

start:
	@echo "Starting $(SERVICE_NAME) systemd service..."
	@sudo systemctl start $(SERVICE_NAME)
	@echo "$(SERVICE_NAME) start command issued. Use 'make status' or 'make logs' to check."

stop:
	@echo "Stopping $(SERVICE_NAME) systemd service..."
	@sudo systemctl stop $(SERVICE_NAME)
	@echo "$(SERVICE_NAME) stop command issued."

restart:
	@echo "Restarting $(SERVICE_NAME) systemd service..."
	@sudo systemctl restart $(SERVICE_NAME)
	@echo "$(SERVICE_NAME) restart command issued. Use 'make status' or 'make logs' to check."

status:
	@echo "Checking status of $(SERVICE_NAME) systemd service..."
	@sudo systemctl status $(SERVICE_NAME) --no-pager

clean:
	@echo "Cleaning systemd service log files..."
	@echo "This will truncate $(SERVICE_LOG_FILE) and $(SERVICE_ERR_FILE)."
	@sudo truncate -s 0 $(SERVICE_LOG_FILE) || echo "Warning: Could not truncate $(SERVICE_LOG_FILE). It might not exist or permissions issue."
	@sudo truncate -s 0 $(SERVICE_ERR_FILE) || echo "Warning: Could not truncate $(SERVICE_ERR_FILE). It might not exist or permissions issue."
	@echo "Service log files have been truncated."

update:
	@echo "Running the update script: $(UPDATE_SCRIPT)..."
	@echo "This will pull changes, update dependencies, and restart the service."
	@bash $(UPDATE_SCRIPT)

help:
	@echo "Available commands for managing the $(SERVICE_NAME) systemd service:"
	@echo "  make logs        - View live logs from the service"
	@echo "  make start       - Start the service"
	@echo "  make stop        - Stop the service"
	@echo "  make restart     - Restart the service"
	@echo "  make status      - Check the status of the service"
	@echo "  make clean       - Clear (truncate) the service log files"
	@echo "  make update      - Run the update script (pulls code, updates deps, restarts service)"

# Default target
default: help
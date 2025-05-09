.PHONY: start stop restart status logs errors clean

SHELL := /bin/bash
PYTHON := python3 # Or just python, depending on your environment
SCRIPT_NAME := auto_scheduler_main.py
LOG_FILE := lifetime_scheduler.log
PID_FILE := scheduler.pid

start:
	@echo "Starting $(SCRIPT_NAME)..."
	@if [ -f $(PID_FILE) ]; then \\
		echo "$(SCRIPT_NAME) is already running (PID: $$(cat $(PID_FILE))). Stop it first with \'make stop\'."; \\
		exit 1; \\
	fi
	@nohup $(PYTHON) $(SCRIPT_NAME) > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@echo "$(SCRIPT_NAME) started with PID $$(cat $(PID_FILE)). Output logged to $(LOG_FILE)."

stop:
	@echo "Stopping $(SCRIPT_NAME)..."
	@if [ -f $(PID_FILE) ]; then \\
		kill $$(cat $(PID_FILE)) && rm -f $(PID_FILE); \\
		echo "$(SCRIPT_NAME) stopped (killed PID $$(cat $(PID_FILE) 2>/dev/null || echo 'unknown')). PID file removed."; \\
	else \\
		echo "PID file $(PID_FILE) not found. Attempting to stop by process name..."; \\
		if pkill -f "$(PYTHON) $(SCRIPT_NAME)"; then \\
			echo "$(SCRIPT_NAME) stopped via pkill."; \\
		else \\
			echo "$(SCRIPT_NAME) process not found or pkill failed."; \\
		fi; \\
	fi

restart: stop
	@sleep 1 # Give it a second to ensure the old process is gone
	$(MAKE) start

status:
	@echo "Checking status of $(SCRIPT_NAME)..."
	@if [ -f $(PID_FILE) ]; then \\
		if ps -p $$(cat $(PID_FILE)) > /dev/null; then \\
			echo "$(SCRIPT_NAME) is running (PID: $$(cat $(PID_FILE)))."; \\
			exit 0; \\
		else \\
			echo "$(SCRIPT_NAME) PID file found, but process is not running. Stale PID file?"; \\
			exit 1; \\
		fi; \\
	else \\
		echo "PID file $(PID_FILE) not found."; \\
		if pgrep -f "$(PYTHON) $(SCRIPT_NAME)" > /dev/null; then \\
			echo "$(SCRIPT_NAME) appears to be running (found via pgrep)."; \\
		else \\
			echo "$(SCRIPT_NAME) does not appear to be running."; \\
		fi; \\
		exit 1; \\
	fi

logs:
	@echo "Displaying last 100 lines of $(LOG_FILE) and tailing..."
	@tail -n 100 $(LOG_FILE)
	@tail -f $(LOG_FILE)

errors:
	@echo "Displaying recent ERROR, CRITICAL, or WARNING lines from $(LOG_FILE)..."
	@tail -n 200 $(LOG_FILE) | grep -E 'ERROR|CRITICAL|WARNING' || echo "No recent errors/warnings found."

clean:
	@echo "Cleaning up log and PID files..."
	@rm -f $(LOG_FILE) $(PID_FILE)
	@echo "Removed $(LOG_FILE) and $(PID_FILE)."

help:
	@echo "Available commands:"
	@echo "  make start    - Start the scheduler daemon"
	@echo "  make stop     - Stop the scheduler daemon"
	@echo "  make restart  - Restart the scheduler daemon"
	@echo "  make status   - Check if the scheduler is running"
	@echo "  make logs     - View live logs (last 100 lines then tail -f)"
	@echo "  make errors   - View recent error/warning messages"
	@echo "  make clean    - Remove log and PID files"

# Default target
default: help 
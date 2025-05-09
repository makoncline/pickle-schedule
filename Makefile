.PHONY: logs

# This Makefile is intended for interacting with the systemd service on the Raspberry Pi.

logs:
	@echo "Showing last 100 lines of systemd service log (/var/log/lifetime-scheduler.log) and tailing..."
	@echo "Note: You might need to run 'sudo make logs' if your user doesn't have permission to read this file directly."
	@tail -n 100 -f /var/log/lifetime-scheduler.log

help:
	@echo "Available commands:"
	@echo "  make logs     - View live logs from the systemd service"

# Default target
default: help
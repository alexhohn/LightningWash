#!/usr/bin/env python3
"""
LightningWash Launcher Script

This script launches the LightningWash system with the configured integration methods:
1. Flask server with BTCPay Server webhook support
2. Bitcoin Switch WebSocket client

Both integration methods can be enabled/disabled via environment variables.
"""

import os
import sys
import time
import signal
import subprocess
import argparse
import logging
from threading import Thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("lightning_wash.log")
    ]
)
logger = logging.getLogger("LightningWash")

# Configuration from environment variables
ENABLE_WEBHOOK = os.environ.get("ENABLE_WEBHOOK_INTEGRATION", "true").lower() == "true"
ENABLE_BITCOINSWITCH = os.environ.get("ENABLE_BITCOINSWITCH_INTEGRATION", "true").lower() == "false"

# Process handles
flask_process = None
websocket_process = None

def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info("Shutting down LightningWash...")
    
    # Terminate processes
    if flask_process:
        logger.info("Stopping Flask server...")
        flask_process.terminate()
        try:
            flask_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            flask_process.kill()
    
    if websocket_process:
        logger.info("Stopping WebSocket client...")
        websocket_process.terminate()
        try:
            websocket_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            websocket_process.kill()
    
    logger.info("Shutdown complete")
    sys.exit(0)

def start_flask_server():
    """Start the Flask server with webhook support."""
    global flask_process
    
    logger.info("Starting Flask server...")
    flask_process = subprocess.Popen(
        [sys.executable, "python/server_pi.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Log Flask server output
    def log_flask_output():
        for line in flask_process.stdout:
            logger.info(f"[Flask] {line.strip()}")
    
    Thread(target=log_flask_output, daemon=True).start()
    
    # Wait for Flask to start
    time.sleep(2)
    
    if flask_process.poll() is not None:
        logger.error("Flask server failed to start")
        return False
    
    logger.info("Flask server started")
    return True

def start_websocket_client():
    """Start the Bitcoin Switch WebSocket client."""
    global websocket_process
    
    logger.info("Starting Bitcoin Switch WebSocket client...")
    websocket_process = subprocess.Popen(
        [sys.executable, "python/btcpay_switch_client.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Log WebSocket client output
    def log_websocket_output():
        for line in websocket_process.stdout:
            logger.info(f"[WebSocket] {line.strip()}")
    
    Thread(target=log_websocket_output, daemon=True).start()
    
    # Wait for WebSocket client to start
    time.sleep(2)
    
    if websocket_process.poll() is not None:
        logger.error("WebSocket client failed to start")
        return False
    
    logger.info("WebSocket client started")
    return True

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="LightningWash Launcher")
    
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Enable BTCPay Server webhook integration"
    )
    
    parser.add_argument(
        "--bitcoinswitch",
        action="store_true",
        help="Enable Bitcoin Switch WebSocket integration"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enable all integration methods"
    )
    
    args = parser.parse_args()
    
    # Override environment variables with command line arguments
    if args.webhook or args.all:
        os.environ["ENABLE_WEBHOOK_INTEGRATION"] = "true"
        global ENABLE_WEBHOOK
        ENABLE_WEBHOOK = True
    
    if args.bitcoinswitch or args.all:
        os.environ["ENABLE_BITCOINSWITCH_INTEGRATION"] = "true"
        global ENABLE_BITCOINSWITCH
        ENABLE_BITCOINSWITCH = True
    
    # If no specific integration is selected, use the environment defaults
    if not args.webhook and not args.bitcoinswitch and not args.all:
        logger.info("Using environment configuration for integrations")
    
    return args

def main():
    """Main function to start the LightningWash system."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting LightningWash...")
    logger.info(f"Webhook integration: {'Enabled' if ENABLE_WEBHOOK else 'Disabled'}")
    logger.info(f"Bitcoin Switch integration: {'Enabled' if ENABLE_BITCOINSWITCH else 'Disabled'}")
    
    # Start the Flask server (always required for API endpoints)
    if not start_flask_server():
        logger.error("Failed to start Flask server. Exiting.")
        return 1
    
    # Start the WebSocket client if enabled
    if ENABLE_BITCOINSWITCH:
        if not start_websocket_client():
            logger.error("Failed to start WebSocket client.")
            # Continue running even if WebSocket client fails
    
    logger.info("LightningWash started successfully")
    
    try:
        # Keep the main thread running
        while True:
            # Check if processes are still running
            if flask_process.poll() is not None:
                logger.error("Flask server has stopped unexpectedly. Exiting.")
                break
            
            if ENABLE_BITCOINSWITCH and websocket_process and websocket_process.poll() is not None:
                logger.warning("WebSocket client has stopped unexpectedly. Restarting...")
                start_websocket_client()
            
            time.sleep(5)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

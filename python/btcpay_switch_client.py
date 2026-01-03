#!/usr/bin/env python3
"""
Bitcoin Switch WebSocket client for LightningWash.
This client connects to the BTCPay Server Bitcoin Switch WebSocket endpoint
and listens for activation messages to control the washing machine.
"""

import os
import json
import time
import signal
import sys
import websocket
import ssl
import logging
import threading
from urllib.parse import urlparse

# Import our shared washing machine control module
import washing_control

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("btcpay_switch.log")
    ]
)
logger = logging.getLogger("BTCPaySwitch")

# Configuration from environment variables
BTCPAY_WEBSOCKET_URL = os.environ.get(
    "BTCPAY_WEBSOCKET_URL", 
    "ws://umbrel.local:3003/apps/32KCJgUTzUBBZD8GJprDxdGMSrXM/pos/bitcoinswitch"
)
ENABLE_BITCOINSWITCH = os.environ.get("ENABLE_BITCOINSWITCH_INTEGRATION", "true").lower() == "true"

# WebSocket connection state
ws = None
should_reconnect = True
reconnect_delay = 5  # Start with 5 seconds delay
max_reconnect_delay = 300  # Maximum 5 minutes delay
reconnect_timer = None

def on_message(ws, message):
    """Handle incoming WebSocket messages."""
    logger.info(f"Received message: {message}")
    
    try:
        # The message is a simple string, not JSON
        data = message
        
        # The Bitcoin Switch plugin sends messages in the format: "io-duration"
        # Where io is the GPIO pin number and duration is the activation time in seconds
        if "-" in data:
            parts = data.split("-")
            if len(parts) == 2:
                pin, duration_str = parts
                
                # Check if the pin matches our relay pin
                if int(pin) == washing_control.RELAY_PIN:
                    try:
                        duration = float(duration_str)
                        
                        # Cap the duration at the maximum allowed value
                        max_duration = washing_control.MAX_WASH_DURATION
                        if duration > max_duration:
                            logger.warning(f"Duration {duration} exceeds maximum allowed ({max_duration}). Capping at {max_duration} seconds.")
                            duration = max_duration
                        
                        logger.info(f"Starting wash cycle for {duration} seconds")
                        
                        # Start the washing machine
                        success = washing_control.start_washing(int(duration))
                        
                        if success:
                            logger.info("Washing machine started successfully")
                        else:
                            logger.warning("Failed to start washing machine")
                    except ValueError:
                        logger.error(f"Invalid duration format: {duration_str}")
                else:
                    logger.warning(f"Received command for pin {pin}, but our relay is on pin {washing_control.RELAY_PIN}")
        else:
            logger.warning(f"Unrecognized message format: {message}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def on_error(ws, error):
    """Handle WebSocket errors."""
    logger.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection close."""
    logger.warning(f"WebSocket connection closed: {close_status_code} - {close_msg}")
    
    if should_reconnect:
        schedule_reconnect()

def on_open(ws):
    """Handle WebSocket connection open."""
    global reconnect_delay
    logger.info("WebSocket connection established")
    # Reset reconnect delay on successful connection
    reconnect_delay = 5

def schedule_reconnect():
    """Schedule a reconnection attempt with exponential backoff."""
    global reconnect_delay, reconnect_timer
    
    if reconnect_timer:
        reconnect_timer.cancel()
    
    logger.info(f"Reconnecting in {reconnect_delay} seconds...")
    reconnect_timer = threading.Timer(reconnect_delay, connect_websocket)
    reconnect_timer.daemon = True
    reconnect_timer.start()
    
    # Exponential backoff with jitter
    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)

def connect_websocket():
    """Connect to the BTCPay Server WebSocket."""
    global ws
    
    try:
        # Parse the URL to check if it's valid
        parsed_url = urlparse(BTCPAY_WEBSOCKET_URL)
        if not parsed_url.netloc:
            logger.error(f"Invalid WebSocket URL: {BTCPAY_WEBSOCKET_URL}")
            return False
        
        # Close existing connection if any
        if ws:
            ws.close()
        
        # Create a new WebSocket connection
        logger.info(f"Connecting to {BTCPAY_WEBSOCKET_URL}")
        ws = websocket.WebSocketApp(
            BTCPAY_WEBSOCKET_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        # Start the WebSocket connection in a separate thread
        wst = threading.Thread(target=ws.run_forever, kwargs={
            'sslopt': {
                "cert_reqs": ssl.CERT_NONE,
                "check_hostname": False,
                "ssl_version": ssl.PROTOCOL_TLSv1_2
            }
        })
        wst.daemon = True
        wst.start()
        
        return True
    except Exception as e:
        logger.error(f"Failed to connect to WebSocket: {e}")
        schedule_reconnect()
        return False

def signal_handler(sig, frame):
    """Handle termination signals."""
    global should_reconnect
    logger.info("Shutting down...")
    should_reconnect = False
    
    if ws:
        ws.close()
    
    if reconnect_timer:
        reconnect_timer.cancel()
    
    sys.exit(0)

def main():
    """Main function to start the Bitcoin Switch client."""
    if not ENABLE_BITCOINSWITCH:
        logger.info("Bitcoin Switch integration is disabled. Set ENABLE_BITCOINSWITCH_INTEGRATION=true to enable.")
        return
    
    if BTCPAY_WEBSOCKET_URL == "wss://example.com/apps/xxxxx/pos/bitcoinswitch":
        logger.warning("Using default WebSocket URL. Please set the BTCPAY_WEBSOCKET_URL environment variable.")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Bitcoin Switch WebSocket client")
    logger.info(f"WebSocket URL: {BTCPAY_WEBSOCKET_URL}")
    logger.info(f"Relay pin: {washing_control.RELAY_PIN}")
    
    # Connect to the WebSocket
    connect_websocket()
    
    try:
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()

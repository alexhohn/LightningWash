#!/usr/bin/env python3
"""
Test script for the Bitcoin Switch WebSocket integration.
This script simulates WebSocket messages from BTCPay Server's Bitcoin Switch plugin.
"""

import argparse
import json
import time
import websocket
import sys

def main():
    parser = argparse.ArgumentParser(description="Test BTCPay Server Bitcoin Switch integration")
    
    parser.add_argument(
        "--url",
        default="ws://localhost:5000/btcpay-switch",
        help="WebSocket URL to connect to (default: ws://localhost:5000/btcpay-switch)"
    )
    
    parser.add_argument(
        "--pin",
        type=int,
        default=17,
        help="GPIO pin number to activate (default: 17)"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds to activate the pin (default: 60)"
    )
    
    args = parser.parse_args()
    
    # Create the message in the format expected by the Bitcoin Switch client
    message = f"{args.pin}-{args.duration}"
    
    print(f"Connecting to {args.url}...")
    print(f"Will send message: {message}")
    
    try:
        # Connect to the WebSocket server
        ws = websocket.create_connection(args.url)
        
        # Send the message as a plain string (not JSON-encoded)
        print(f"Sending message: {message}")
        ws.send(message)
        
        # Wait for a response (optional)
        print("Waiting for response...")
        result = ws.recv()
        print(f"Received: {result}")
        
        # Close the connection
        ws.close()
        
        print("Test completed successfully")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

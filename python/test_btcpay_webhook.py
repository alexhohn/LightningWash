#!/usr/bin/env python3
"""
Test script to simulate BTCPay Server webhook requests.
This helps test the webhook integration without needing a real BTCPay Server instance.
"""

import requests
import json
import hmac
import hashlib
import argparse
import os
import time

# Default values
DEFAULT_URL = "http://localhost:5000/btcpay-webhook"
DEFAULT_SECRET = "btcpay-webhook-secret"  # Should match BTCPAY_WEBHOOK_SECRET in server_pi.py

def create_signature(payload, secret):
    """Create a BTCPay Server compatible webhook signature."""
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"

def send_webhook(url, payload, secret):
    """Send a simulated webhook request to the server."""
    payload_json = json.dumps(payload)
    headers = {
        'Content-Type': 'application/json',
        'BTCPay-Sig': create_signature(payload_json, secret)
    }
    
    print(f"Sending webhook to {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload_json}")
    
    response = requests.post(url, data=payload_json, headers=headers)
    
    print(f"Response status code: {response.status_code}")
    print(f"Response body: {response.text}")
    
    return response

def create_invoice_settled_payload(invoice_id="test-invoice-123", duration_seconds=60):
    """Create a payload for an invoice settled event."""
    return {
        "invoiceId": invoice_id,
        "type": "InvoiceSettled",
        "metadata": {
            "washDuration": duration_seconds
        },
        "amount": duration_seconds,  # Fallback if metadata is not used
        "currency": "BTC",
        "status": "Settled",
        "timestamp": int(time.time())
    }

def create_invoice_refunded_payload(invoice_id="test-invoice-123"):
    """Create a payload for an invoice refunded event."""
    return {
        "invoiceId": invoice_id,
        "type": "InvoiceRefunded",
        "status": "Refunded",
        "timestamp": int(time.time())
    }

def main():
    parser = argparse.ArgumentParser(description='Simulate BTCPay Server webhook requests')
    parser.add_argument('--url', default=DEFAULT_URL, help='URL of the webhook endpoint')
    parser.add_argument('--secret', default=DEFAULT_SECRET, help='Webhook secret')
    parser.add_argument('--event', choices=['paid', 'refunded'], default='paid', help='Event type to simulate')
    parser.add_argument('--invoice-id', default=f"test-invoice-{int(time.time())}", help='Invoice ID')
    parser.add_argument('--duration', type=int, default=60, help='Wash duration in seconds (for paid event)')
    
    args = parser.parse_args()
    
    # Use environment variable if available
    secret = os.environ.get("BTCPAY_WEBHOOK_SECRET", args.secret)
    
    if args.event == 'paid':
        payload = create_invoice_settled_payload(args.invoice_id, args.duration)
        print(f"Simulating invoice paid event for {args.duration} seconds")
    else:
        payload = create_invoice_refunded_payload(args.invoice_id)
        print(f"Simulating invoice refunded event")
    
    send_webhook(args.url, payload, secret)

if __name__ == "__main__":
    main()

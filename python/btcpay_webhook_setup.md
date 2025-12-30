# BTCPay Server Webhook Integration for LightningWash

This document explains how to set up the webhook integration between your BTCPay Server and the Raspberry Pi washing machine controller.

## Overview

The integration works as follows:

1. Customer scans a QR code at the washing station
2. BTCPay Server generates an invoice with the selected wash duration
3. Customer pays the invoice via Lightning Network
4. BTCPay Server sends a webhook notification to your Raspberry Pi
5. Raspberry Pi activates the washing machine for the specified duration
6. If a refund is requested, BTCPay Server sends another webhook and the washing machine stops

## Configuration Steps

### 1. Set Environment Variables on Raspberry Pi

For security, set these environment variables on your Raspberry Pi:

```bash
# Your washing machine secret key
export WASHING_MACHINE_SECRET="your-secure-secret-here"

# A secret key for BTCPay Server webhooks
export BTCPAY_WEBHOOK_SECRET="your-btcpay-webhook-secret-here"
```

For persistence, add these to your `.bashrc` or create a startup script.

### 2. Configure BTCPay Server Webhook

1. Log in to your BTCPay Server admin interface
2. Go to "Store Settings" > "Webhooks"
3. Click "Add New Webhook"
4. Configure the webhook:
   - **Payload URL**: `http://your-raspberry-pi-ip:5000/btcpay-webhook`
   - **Secret**: Enter the same value as your `BTCPAY_WEBHOOK_SECRET` environment variable
   - **Events to send**: Select at minimum:
     - `Invoice settled` (to start the washing machine)
     - `Invoice payment settled` (alternative event that might be triggered)
     - `Invoice refunded` (to stop the washing machine if refunded)
     - `Invoice payment refunded` (alternative refund event)
5. Click "Add Webhook"

### 3. Configure Invoice Metadata

For the washing duration to be properly communicated, you need to include it in the invoice metadata when creating invoices. There are two ways to do this:

#### Option 1: Include Duration in Metadata

When creating an invoice through the BTCPay API, include the wash duration in seconds in the metadata:

```json
{
  "metadata": {
    "washDuration": 300  // 5 minutes in seconds
  }
}
```

#### Option 2: Use Amount-Based Duration

If not specifying duration in metadata, the system will use the payment amount to determine duration:
- 1 satoshi = 1 second of washing time
- Maximum duration is capped at 1 hour (3600 seconds)

### 4. Testing the Integration

1. Start your Flask server on the Raspberry Pi:
   ```bash
   cd /path/to/your/project
   python server_pi.py
   ```

2. Create a test invoice in BTCPay Server with metadata including washDuration
3. Pay the invoice
4. Verify that the webhook is received and the washing machine starts

## Troubleshooting

### Webhook Not Received

- Check that your Raspberry Pi is accessible from the internet or your local network
- Verify the webhook URL is correct in BTCPay Server
- Check that port 5000 is open on your Raspberry Pi
- Look for webhook delivery attempts in BTCPay Server logs

### Webhook Received But Washing Machine Doesn't Start

- Check the Flask server logs for errors
- Verify that the webhook signature is being validated correctly
- Ensure the duration is being properly extracted from the invoice

### Security Considerations

- For production use, consider setting up HTTPS for your webhook endpoint
- Regularly rotate your webhook secret
- Ensure your Raspberry Pi has proper network security measures in place

## Advanced Configuration

### Custom Duration Mapping

If you want to customize how payment amounts map to washing durations, modify the `extract_invoice_data` function in `server_pi.py`.

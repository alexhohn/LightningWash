from flask import Flask, request, jsonify
import time
import os
import hmac
import hashlib
import json
from functools import wraps

# Import our shared washing machine control module
import washing_control


# --- Configuration from Environment Variables ---
# BTCPay Server webhook configuration
BTCPAY_WEBHOOK_SECRET = os.environ.get("BTCPAY_WEBHOOK_SECRET", "btcpay-webhook-secret")
if BTCPAY_WEBHOOK_SECRET == "btcpay-webhook-secret":
    print("SÉCURITÉ : Vous utilisez la clé webhook par défaut. Définissez la variable d'environnement BTCPAY_WEBHOOK_SECRET.")

# Enable/disable webhook integration
ENABLE_WEBHOOK = os.environ.get("ENABLE_WEBHOOK_INTEGRATION", "true").lower() == "true"

# Get references to shared variables and functions
SECRET_KEY = washing_control.SECRET_KEY
MAX_WASH_DURATION = washing_control.MAX_WASH_DURATION

# Create Flask app
app = Flask(__name__)


# --- Authentication Decorator ---
def require_secret(f):
    """A decorator to secure endpoints with our secret key."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.json
        # Check if JSON exists and if the secret matches
        if not data or data.get('secret') != SECRET_KEY:
            return jsonify({"error": "Acces non autorise ou cle secrete invalide"}), 403 # Forbidden
        return f(*args, **kwargs)
    return decorated_function


# --- BTCPay Server Webhook Functions ---
def verify_btcpay_signature(request_data, signature_header):
    """Verify that the webhook request is coming from BTCPay Server."""
    if not signature_header:
        return False
    
    # The signature header format is: sha256=hex_signature
    if not signature_header.startswith('sha256='):
        return False
    
    signature = signature_header[7:]  # Remove 'sha256=' prefix
    
    # Create a new HMAC with our secret
    mac = hmac.new(
        BTCPAY_WEBHOOK_SECRET.encode('utf-8'),
        msg=request_data,
        digestmod=hashlib.sha256
    )
    
    # Compare our signature with the one in the header
    expected_signature = mac.hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def extract_invoice_data(payload):
    """Extract relevant data from BTCPay Server invoice webhook payload."""
    try:
        # Extract invoice ID
        invoice_id = payload.get('invoiceId', '')
        
        # Extract payment status
        status = payload.get('type', '')  # e.g., "InvoiceSettled", "InvoiceExpired"
        
        # Extract metadata for duration
        metadata = payload.get('metadata', {})
        duration_seconds = metadata.get('washDuration', 0)
        
        # If duration is not in metadata, try to calculate from price
        if not duration_seconds and 'amount' in payload:
            # Example: 1 satoshi = 1 second of washing
            # You'll need to adjust this conversion based on your pricing model
            price_in_sats = payload.get('amount', 0)
            duration_seconds = min(int(price_in_sats), MAX_WASH_DURATION)
        
        return {
            'invoice_id': invoice_id,
            'status': status,
            'duration_seconds': duration_seconds
        }
    except Exception as e:
        print(f"Error extracting invoice data: {e}")
        return None


def handle_invoice_paid(invoice_data):
    """Handle a paid invoice by starting the washing machine."""
    invoice_id = invoice_data.get('invoice_id', '')
    duration_seconds = invoice_data.get('duration_seconds', 0)
    
    if not duration_seconds or duration_seconds <= 0:
        print(f"Invalid duration for invoice {invoice_id}: {duration_seconds}")
        return False
    
    # Track this invoice for potential refunds
    washing_control.track_invoice(invoice_id, duration_seconds)
    
    # Start the washing machine
    success = washing_control.start_washing(duration_seconds)
    
    if success:
        print(f"Washing machine started for invoice {invoice_id} with duration {duration_seconds}s")
    else:
        print(f"Failed to start washing machine for invoice {invoice_id}")
        
    return success


def handle_invoice_refunded(invoice_data):
    """Handle a refunded invoice by stopping the washing machine."""
    invoice_id = invoice_data.get('invoice_id', '')
    
    if invoice_id not in washing_control.active_invoices:
        print(f"Invoice {invoice_id} not found in active invoices")
        return False
    
    # Stop the washing machine
    success = washing_control.stop_washing()
    
    if success:
        print(f"Washing machine stopped for refunded invoice {invoice_id}")
        # Remove from active invoices
        washing_control.remove_invoice(invoice_id)
    else:
        print(f"Failed to stop washing machine for refunded invoice {invoice_id}")
        
    return success

# --- Endpoints ---

@app.route('/status', methods=['GET'])
def get_status():
    status_data = washing_control.get_status()
    return jsonify(status_data)

@app.route('/start-wash', methods=['POST'])
@require_secret
def start_wash():
    data = request.json  # We know this exists because the decorator checked it
    duration_seconds = data.get('duration', 0)
    
    # Input validation for duration
    if not isinstance(duration_seconds, int) or not (0 < duration_seconds <= MAX_WASH_DURATION):
        return jsonify({"error": f"Duree invalide. Doit etre un nombre entier entre 1 et {MAX_WASH_DURATION} secondes."}), 400
    
    success = washing_control.start_washing(duration_seconds)
    
    if success:
        return jsonify({"status": "Lavage démarre"})
    else:
        return jsonify({"error": "Lavage deja en cours d'utilisation"}), 409

@app.route('/add-time', methods=['POST'])
@require_secret
def add_time():
    """Add time to a running washing machine."""
    data = request.json  # We know this exists because the decorator checked it
    duration_seconds = data.get('duration', 0)
    
    # Input validation for duration
    if not isinstance(duration_seconds, int) or not (0 < duration_seconds <= MAX_WASH_DURATION):
        return jsonify({"error": f"Duree invalide. Doit etre un nombre entier entre 1 et {MAX_WASH_DURATION} secondes."}), 400
    
    success = washing_control.add_washing_time(duration_seconds)
    
    if success:
        return jsonify({"status": "Temps ajouté au lavage en cours"})
    else:
        return jsonify({"error": "Aucun lavage en cours pour ajouter du temps"}), 404

@app.route('/stop-wash', methods=['POST'])
@require_secret
def stop_wash():
    success = washing_control.stop_washing()
    
    if success:
        return jsonify({"status": "Signal d'arrêt envoyé"})
    else:
        return jsonify({"status": "Aucun lavage en cours a arreter"}), 404


@app.route('/btcpay-webhook', methods=['POST'])
def btcpay_webhook():
    """Handle webhook notifications from BTCPay Server."""
    if not ENABLE_WEBHOOK:
        return jsonify({"error": "Webhook integration is disabled"}), 503
    
    # Get the raw request data for signature verification
    request_data = request.get_data()
    
    # Get the signature from the headers
    signature_header = request.headers.get('BTCPay-Sig')
    
    # Verify the signature
    if not verify_btcpay_signature(request_data, signature_header):
        print("⚠️ Invalid BTCPay webhook signature")
        return jsonify({"error": "Invalid signature"}), 401
    
    # Parse the JSON payload
    try:
        payload = request.json
        if not payload:
            return jsonify({"error": "Empty payload"}), 400
        
        # Extract invoice data
        invoice_data = extract_invoice_data(payload)
        if not invoice_data:
            return jsonify({"error": "Could not extract invoice data"}), 400
        
        # Handle different event types
        event_type = payload.get('type', '')
        
        if event_type == 'InvoiceSettled' or event_type == 'InvoicePaymentSettled':
            # Invoice has been paid, start the washing machine
            success = handle_invoice_paid(invoice_data)
            if success:
                return jsonify({"status": "Washing machine started"}), 200
            else:
                return jsonify({"error": "Failed to start washing machine"}), 500
                
        elif event_type == 'InvoiceRefunded' or event_type == 'InvoicePaymentRefunded':
            # Invoice has been refunded, stop the washing machine
            success = handle_invoice_refunded(invoice_data)
            if success:
                return jsonify({"status": "Washing machine stopped"}), 200
            else:
                return jsonify({"error": "Failed to stop washing machine"}), 500
                
        else:
            # Unhandled event type
            print(f"Unhandled BTCPay event type: {event_type}")
            return jsonify({"status": "Event acknowledged but not processed"}), 200
            
    except Exception as e:
        print(f"Error processing BTCPay webhook: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Print integration status
    if ENABLE_WEBHOOK:
        print("BTCPay Server webhook integration is enabled")
    else:
        print("BTCPay Server webhook integration is disabled")
    
    # This part is for development only!
    app.run(host='0.0.0.0', port=5000)

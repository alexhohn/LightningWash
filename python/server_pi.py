from flask import Flask, request, jsonify
import time
import threading
import os
import hmac
import hashlib
import json
from functools import wraps
from threading import Event 

# --- Logique d'importation portable ---
IS_RASPBERRY_PI = True
try:
    import RPi.GPIO as GPIO
    print("✅ Librairie RPi.GPIO chargée. Mode Raspberry Pi activé.")
except (ImportError, RuntimeError):
    import mock_gpio as GPIO
    IS_RASPBERRY_PI = False
    print("⚠️  ATTENTION : Librairie RPi.GPIO non trouvée. Mode simulation activé.")
    print("Les commandes GPIO seront affichées dans la console.")


# --- [IMPROVED] Configuration from Environment Variables ---
# Load the secret key from an environment variable. If not set, use a default (unsafe) key.
SECRET_KEY = os.environ.get("WASHING_MACHINE_SECRET", "default-unsafe-secret")
if SECRET_KEY == "default-unsafe-secret":
    print("SÉCURITÉ : Vous utilisez la clé secrète par défaut. Définissez la variable d'environnement WASHING_MACHINE_SECRET.")

# BTCPay Server webhook configuration
BTCPAY_WEBHOOK_SECRET = os.environ.get("BTCPAY_WEBHOOK_SECRET", "btcpay-webhook-secret")
if BTCPAY_WEBHOOK_SECRET == "btcpay-webhook-secret":
    print("SÉCURITÉ : Vous utilisez la clé webhook par défaut. Définissez la variable d'environnement BTCPAY_WEBHOOK_SECRET.")

# Define a reasonable maximum duration in seconds (e.g., 1 hour)
MAX_WASH_DURATION = 1 * 60 * 60 

# Invoice tracking for refunds
active_invoices = {}  # Store invoice_id -> {start_time, duration, etc.}

# --- GPIO and App Setup ---
RELAY_PIN = 17 
MAINTENANCE_SWITCH_PIN = 18

app = Flask(__name__)

# --- GESTION DE L'ÉTAT ---
current_status = "idle"
status_lock = threading.Lock()
wash_end_time = None
total_duration = 0
stop_event = Event()

# --- Configuration des broches GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, GPIO.LOW)
GPIO.setup(MAINTENANCE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


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
    
    # Start the washing machine
    payload = {
        'secret': SECRET_KEY,
        'duration': duration_seconds
    }
    
    # Track this invoice for potential refunds
    active_invoices[invoice_id] = {
        'start_time': time.time(),
        'duration': duration_seconds
    }
    
    # Call our existing start_wash function
    with app.test_request_context(
        '/start-wash',
        method='POST',
        json=payload
    ):
        response = start_wash()
        success = isinstance(response, tuple) and response[1] == 200 if isinstance(response, tuple) else True
        
        if success:
            print(f"Washing machine started for invoice {invoice_id} with duration {duration_seconds}s")
        else:
            print(f"Failed to start washing machine for invoice {invoice_id}")
            
        return success


def handle_invoice_refunded(invoice_data):
    """Handle a refunded invoice by stopping the washing machine."""
    invoice_id = invoice_data.get('invoice_id', '')
    
    if invoice_id not in active_invoices:
        print(f"Invoice {invoice_id} not found in active invoices")
        return False
    
    # Stop the washing machine
    payload = {
        'secret': SECRET_KEY
    }
    
    # Call our existing stop_wash function
    with app.test_request_context(
        '/stop-wash',
        method='POST',
        json=payload
    ):
        response = stop_wash()
        success = isinstance(response, tuple) and response[1] == 200 if isinstance(response, tuple) else True
        
        if success:
            print(f"Washing machine stopped for refunded invoice {invoice_id}")
            # Remove from active invoices
            if invoice_id in active_invoices:
                del active_invoices[invoice_id]
        else:
            print(f"Failed to stop washing machine for refunded invoice {invoice_id}")
            
        return success


# --- Fonctions existantes lit l'état de de l'interrupteur manuel ---
def read_external_sensor():
    """Lit le fichier qui simule notre capteur externe (monnayeur)."""
    try:
        with open("external_status.txt", "r") as f:
            return f.read().strip().upper()
    except FileNotFoundError:
        return "OFF"

def wash_cycle(duration):
    global current_status, status_lock, wash_end_time, total_duration, stop_event
    print(f"Cycle de lavage démarré pour {duration} secondes.")
    
    try:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        was_stopped = stop_event.wait(timeout=duration)
        if was_stopped:
            print("Le lavage a ete arrete manuellement avant la fin.")
        else:
            print("Lavage termine normalement.")
    finally:
        # Ensure the relay is always turned off.
        GPIO.output(RELAY_PIN, GPIO.LOW)
        # Reset state
        with status_lock:
            current_status = "idle"
            wash_end_time = None
            total_duration = 0
        print("Statut repassé à 'idle'.")

# --- Endpoints ---

@app.route('/status', methods=['GET'])
def get_status():
    external_state = read_external_sensor()
    
    with status_lock:
        if current_status == "busy" or external_state == "ON":
            remaining_time = 0
            if wash_end_time is not None:
                remaining_time = max(0, round(wash_end_time - time.time()))

            return jsonify({
                "status": "busy", 
                "remaining_time": remaining_time,
                "total_duration": total_duration
            })
    
    return jsonify({"status": "idle"})

@app.route('/start-wash', methods=['POST'])
@require_secret  # [IMPROVED] Using the decorator for authentication
def start_wash():
    global current_status, status_lock, wash_end_time, total_duration, stop_event
    
    external_state = read_external_sensor()
    data = request.json # We know this exists because the decorator checked it

    with status_lock:
        if current_status != "idle" or external_state == "ON":
            return jsonify({"error": "Lavage deja en cours d'utilisation"}), 409

        duration_seconds = data.get('duration', 0)
        
        # [IMPROVED] Input validation for duration
        if not isinstance(duration_seconds, int) or not (0 < duration_seconds <= MAX_WASH_DURATION):
            return jsonify({"error": f"Duree invalide. Doit etre un nombre entier entre 1 et {MAX_WASH_DURATION} secondes."}), 400

        stop_event.clear()
        current_status = "busy"     
        wash_end_time = time.time() + duration_seconds
        total_duration = duration_seconds
        
        print(f"Machine verrouillée. Lavage de {duration_seconds}s. Fin prévue à {wash_end_time}.")
        
        wash_thread = threading.Thread(target=wash_cycle, args=(duration_seconds,))
        wash_thread.start()

        return jsonify({"status": "Lavage démarre"})

#Fonction à dev pour ajouter du temps à un lavage déjà en cours.
""" 
@app.route('/add-time', methods=['POST'])
# Is machine busy ? 2. Is it runing or in maintenance ? 3. If runing add time to the timer corresponding to the time paid.
@require_secret # [IMPROVED] This endpoint is now protected!
def add_time():
        global current_status, status_lock, wash_end_time, total_duration, stop_event
        external_state = read_external_sensor()

        if current_status == "busy" :
            stop_event.set() 
"""


@app.route('/stop-wash', methods=['POST'])
@require_secret # [IMPROVED] This endpoint is now protected!
def stop_wash():
    global stop_event
    
    if current_status == "busy":
        print("🔴 Ordre d'arrêt d'urgence reçu !")
        stop_event.set()
        return jsonify({"status": "Signal d'arrêt envoyé"})
        
    return jsonify({"status": "Aucun lavage en cours a arreter"}), 404


@app.route('/btcpay-webhook', methods=['POST'])
def btcpay_webhook():
    """Handle webhook notifications from BTCPay Server."""
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
    # This part is for development only!
    app.run(host='0.0.0.0', port=5000)

from flask import Flask, request, jsonify
import time
import threading
import os
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

# Define a reasonable maximum duration in seconds (e.g., 3 hours)
MAX_WASH_DURATION = 3 * 60 * 60 

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


# --- [NEW] Authentication Decorator ---
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


if __name__ == '__main__':
    # This part is for development only!
    app.run(host='0.0.0.0', port=5000)

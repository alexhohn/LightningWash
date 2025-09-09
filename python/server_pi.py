from flask import Flask, request, jsonify
import time
import threading

from threading import Event 

# --- Logique d'importation portable ---
IS_RASPBERRY_PI = True
try:
    # On essaie d'importer la VRAIE librairie
    import RPi.GPIO as GPIO
    print("✅ Librairie RPi.GPIO chargée. Mode Raspberry Pi activé.")
except (ImportError, RuntimeError):
    # Si ça échoue, on importe notre FAUX module
    import mock_gpio as GPIO
    IS_RASPBERRY_PI = False
    print("⚠️  ATTENTION : Librairie RPi.GPIO non trouvée. Mode simulation activé.")
    print("Les commandes GPIO seront affichées dans la console.")


# --- Configuration ---
RELAY_PIN = 17 
MAINTENANCE_SWITCH_PIN = 18
SECRET_KEY = "VOTRE_SECRET_SUPER_UNIQUE_ICI"

app = Flask(__name__)

# --- GESTION DE L'ÉTAT ---
current_status = "idle"
status_lock = threading.Lock()
wash_end_time = None # [AJOUTÉ] Pour stocker le timestamp de la fin du lavage
total_duration = 0   # [AJOUTÉ] Pour stocker la durée totale du cycle en cours
stop_event = Event()

# --- Configuration des broches GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, GPIO.LOW)
GPIO.setup(MAINTENANCE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)





# --- NOUVELLE FONCTION : Lire le capteur externe ---
def read_external_sensor():
    """Lit le fichier qui simule notre capteur externe (monnayeur)."""
    try:
        with open("external_status.txt", "r") as f:
            status = f.read().strip().upper()
            return status
    except FileNotFoundError:
        # Si le fichier n'existe pas, on considère que le capteur est sur OFF
        return "OFF"

# --- Fonction pour le lavage (pour la lancer en arrière-plan) ---
def wash_cycle(duration):
    global current_status, status_lock, wash_end_time, total_duration, stop_event

    print(f"Cycle de lavage démarré pour {duration} secondes.")
    
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    
    # [MODIFIÉ] Au lieu de time.sleep(), on utilise wait() qui est interruptible.
    # Il attendra "duration" secondes, mais s'arrêtera si stop_event.set() est appelé.
    was_stopped = stop_event.wait(timeout=duration)
    
    GPIO.output(RELAY_PIN, GPIO.LOW)
    
    if was_stopped:
        print("Le lavage a ete arrete manuellement avant la fin.")
    else:
        print(" Lavage termine normalement.")

    # Réinitialisation de l'état
    with status_lock:
        current_status = "idle"
        wash_end_time = None
        total_duration = 0
    print("Statut repassé à 'idle'.")

# --- Endpoint pour le statut (maintenant plus intelligent) ---
@app.route('/status', methods=['GET'])
def get_status():
    global current_status, wash_end_time, total_duration

    # On lit l'état du capteur externe
    external_state = read_external_sensor()
    # On verifie si la machine est déjà en cours de lavage
    if current_status == "busy" or external_state == "ON":
        remaining_time = 0
    
    # On calcule le temps restant uniquement si le lavage a été lancé par notre script
        if wash_end_time is not None:
            # Calcule la différence et s'assure qu'elle n'est pas négative
            remaining_time = max(0, round(wash_end_time - time.time()))

        return jsonify({
            "status": "busy", 
            "remaining_time": remaining_time,    # Temps restant en secondes
            "total_duration": total_duration     # Durée totale du cycle
        })
    # Si aucune des conditions ci-dessus n'est remplie, la machine est libre
    return jsonify({"status": "idle"})

# --- Endpoint pour démarrer le lavage (maintenant plus sécurisé) ---
@app.route('/start-wash', methods=['POST'])
def start_wash():
    global current_status, status_lock, wash_end_time, total_duration, stop_event
    # On lit l'état du capteur externe
    external_state = read_external_sensor()
    # On utilise le "lock" pour s'assurer qu'une seule requête à la fois peut changer le statut
    with status_lock:
        # 1. Vérification de l'état AVANT TOUTE CHOSE
        if current_status != "idle" or external_state == "ON":
            return jsonify({"error": "Lavage deja en cours d'utilisation"}), 409 # 409 est le code HTTP pour "Conflit"
        
        # 2. Validation de la requête
        data = request.json
        if not data or data.get('secret') != SECRET_KEY: # Vérification du secret
            return jsonify({"error": "Acces non autorise"}), 403

        duration_seconds = data.get('duration', 0)
        if duration_seconds <= 0: # Vérification de la durée
            return jsonify({"error": "Duree invalide"}), 400

        duration_seconds = data.get('duration', 0) #On obtient la durée demandée

        # On s'assure que le drapeau est baissé avant de commencer
        stop_event.clear()

        # 3. On verrouille la machine IMMÉDIATEMENT
        current_status = "busy"     
        wash_end_time = time.time() + duration_seconds # On met à jour le timestamp de la fin du lavage
        total_duration = duration_seconds
        
        print(f"Machine verrouillée. Lavage de {duration_seconds}s. Fin prévue à {wash_end_time}.")
        
        wash_thread = threading.Thread(target=wash_cycle, args=(duration_seconds,))
        wash_thread.start()

        return jsonify({"status": "Lavage démarre"})


@app.route('/stop-wash', methods=['POST'])
def stop_wash():
    global stop_event
    if current_status == "busy":
        print("🔴 Ordre d'arrêt d'urgence reçu !")
        stop_event.set() # On lève le drapeau d'arrêt
        return jsonify({"status": "Signal d'arrêt envoyé"})
    return jsonify({"status": "Aucun lavage en cours à arrêter"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
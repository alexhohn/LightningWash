#!/usr/bin/env python3
"""
Shared washing machine control module for LightningWash.
This module contains common functionality used by both the Flask server
and the Bitcoin Switch WebSocket client.
"""

import time
import threading
import os
from threading import Event, Lock

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

# --- Configuration from Environment Variables ---
# Load the secret key from an environment variable. If not set, use a default (unsafe) key.
SECRET_KEY = os.environ.get("WASHING_MACHINE_SECRET", "default-unsafe-secret")
if SECRET_KEY == "default-unsafe-secret":
    print("SÉCURITÉ : Vous utilisez la clé secrète par défaut. Définissez la variable d'environnement WASHING_MACHINE_SECRET.")

# Define a reasonable maximum duration in seconds (e.g., 1 hour)
MAX_WASH_DURATION = int(os.environ.get("MAX_WASH_DURATION", 3600))  # 1 hour default

# --- GPIO Setup ---
RELAY_PIN = int(os.environ.get("RELAY_PIN", 17))
MAINTENANCE_SWITCH_PIN = int(os.environ.get("MAINTENANCE_SWITCH_PIN", 18))

# --- GESTION DE L'ÉTAT ---
current_status = "idle"
status_lock = Lock()
wash_end_time = None
total_duration = 0
stop_event = Event()

# Invoice tracking for refunds
active_invoices = {}  # Store invoice_id -> {start_time, duration, etc.}

# Initialize GPIO
def init_gpio():
    """Initialize GPIO pins for the washing machine."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    GPIO.output(RELAY_PIN, GPIO.LOW)
    GPIO.setup(MAINTENANCE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"GPIO initialized: Relay pin={RELAY_PIN}, Maintenance switch pin={MAINTENANCE_SWITCH_PIN}")

# --- Fonctions existantes lit l'état de de l'interrupteur manuel ---
def read_external_sensor():
    """Lit le fichier qui simule notre capteur externe (monnayeur)."""
    try:
        with open("external_status.txt", "r") as f:
            return f.read().strip().upper()
    except FileNotFoundError:
        return "OFF"

def wash_cycle(duration):
    """Run a washing cycle for the specified duration."""
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

def add_washing_time(duration_seconds):
    """Add time to a running washing machine."""
    global current_status, status_lock, wash_end_time, total_duration
    
    if not isinstance(duration_seconds, int) or not (0 < duration_seconds <= MAX_WASH_DURATION):
        print(f"Durée invalide: {duration_seconds}. Doit être entre 1 et {MAX_WASH_DURATION} secondes.")
        return False
    
    with status_lock:
        if current_status != "busy":
            print("Aucun lavage en cours pour ajouter du temps")
            return False
        
        # Calculate remaining time
        remaining_time = max(0, wash_end_time - time.time())
        
        # Add the new duration to the remaining time
        new_remaining_time = remaining_time + duration_seconds
        
        # Update the wash end time
        wash_end_time = time.time() + new_remaining_time
        
        # Update the total duration
        total_duration += duration_seconds
        
        print(f"Temps ajouté: {duration_seconds}s. Nouveau temps restant: {new_remaining_time}s. Fin prévue à {wash_end_time}.")
        
        return True

def start_washing(duration_seconds):
    """Start the washing machine for the specified duration."""
    global current_status, status_lock, wash_end_time, total_duration, stop_event
    
    if not isinstance(duration_seconds, int) or not (0 < duration_seconds <= MAX_WASH_DURATION):
        print(f"Durée invalide: {duration_seconds}. Doit être entre 1 et {MAX_WASH_DURATION} secondes.")
        return False
    
    external_state = read_external_sensor()
    
    with status_lock:
        # If the washing machine is already running, add time instead of starting a new cycle
        if current_status == "busy":
            print("Lavage déjà en cours, ajout de temps...")
            return add_washing_time(duration_seconds)
        
        # If the external sensor indicates the machine is in use, we can't start
        if external_state == "ON":
            print("Machine en maintenance ou utilisée manuellement")
            return False
            
        stop_event.clear()
        current_status = "busy"     
        wash_end_time = time.time() + duration_seconds
        total_duration = duration_seconds
        
        print(f"Machine verrouillée. Lavage de {duration_seconds}s. Fin prévue à {wash_end_time}.")
        
        wash_thread = threading.Thread(target=wash_cycle, args=(duration_seconds,))
        wash_thread.daemon = True  # Make thread exit when main program exits
        wash_thread.start()
        
        return True

def stop_washing():
    """Stop the washing machine if it's running."""
    global stop_event, current_status
    
    if current_status == "busy":
        print("🔴 Ordre d'arrêt d'urgence reçu !")
        stop_event.set()
        return True
    else:
        print("Aucun lavage en cours à arrêter")
        return False

def get_status():
    """Get the current status of the washing machine."""
    external_state = read_external_sensor()
    
    with status_lock:
        if current_status == "busy" or external_state == "ON":
            remaining_time = 0
            if wash_end_time is not None:
                remaining_time = max(0, round(wash_end_time - time.time()))

            return {
                "status": "busy", 
                "remaining_time": remaining_time,
                "total_duration": total_duration
            }
    
    return {"status": "idle"}

def track_invoice(invoice_id, duration):
    """Track an invoice for potential refunds."""
    active_invoices[invoice_id] = {
        'start_time': time.time(),
        'duration': duration
    }

def remove_invoice(invoice_id):
    """Remove an invoice from tracking."""
    if invoice_id in active_invoices:
        del active_invoices[invoice_id]

# Initialize GPIO on module import
init_gpio()

# Fichier de simulation pour la librairie RPi.GPIO
# Il nous permet de faire tourner le code du Pi sur un PC/Mac.

# On définit des fausses constantes
BCM = 1
OUT = 1
IN = 1
PUD_UP = 1
HIGH = 1
LOW = 0

# On définit des fausses fonctions qui ne font qu'imprimer des messages
def setmode(mode):
    print(f"[MOCK_GPIO] Mode des broches réglé sur : {mode}")

def setup(pin, mode, pull_up_down=None):
    print(f"[MOCK_GPIO] Broche {pin} configurée en mode {mode}")

def output(pin, state):
    if state == HIGH:
        print(f"[MOCK_GPIO] BROCHE {pin} : ON (état HIGH)")
    else:
        print(f"[MOCK_GPIO] BROCHE {pin} : OFF (état LOW)")

def input(pin):
    # Pour simuler l'interrupteur de maintenance, on retourne HIGH (opérationnel)
    # Vous pouvez changer cette valeur pour tester le mode maintenance.
    print(f"[MOCK_GPIO] Lecture de la broche {pin}... retourne HIGH (Opérationnel)")
    return HIGH

def cleanup():
    print("[MOCK_GPIO] Nettoyage des broches GPIO.")
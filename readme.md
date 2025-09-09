# ⚡ LightningWash 🚗 (Vibecoded with Gemini)

**LightningWash** est le logiciel de contrôle pour un système de car wash automatisé acceptant les paiements via le Lightning Network de Bitcoin. Ce projet est conçu pour tourner sur un Raspberry Pi connecté physiquement au car wash, tout en offrant une API web pour le contrôle à distance.

Ce code a été développé pour permettre une simulation complète sur un ordinateur de développement (PC/Mac) avant son déploiement sur le matériel cible.



---

## Fonctionnalités ✨

* **Serveur API Web** : Basé sur Python et Flask, il expose des endpoints pour contrôler et superviser le car wash.
* **Gestion d'État Complète** : Le système gère plusieurs états (`idle`, `busy`, `maintenance`) pour éviter les conflits et assurer un fonctionnement robuste.
* **Contrôle à Distance** :
    * **`/start-wash`** : Pour démarrer un cycle de lavage après un paiement.
    * **`/stop-wash`** : Un arrêt d'urgence pour interrompre immédiatement un cycle.
    * **`/status`** : Pour obtenir l'état en temps réel de la machine, y compris le temps restant.
* **Simulation Matérielle** : Peut fonctionner sans le matériel Raspberry Pi grâce à un module de simulation (`mock_gpio.py`) pour un développement et des tests facilités.
* **Détection d'Événements Externes** : Simule la détection d'un paiement externe (ex: monnayeur) via un fichier "capteur" pour synchroniser l'état de la machine.
* **Sécurité** : Utilise une clé secrète simple pour sécuriser les endpoints qui déclenchent des actions.

---

##  Prérequis 🛠️

* **Python 3.7+**
* **Librairie Flask** (`pip install Flask`)
* **Sur un Raspberry Pi :** La librairie `RPi.GPIO` (`pip install RPi.GPIO`)

---

## Installation et Configuration

1.  **Clonez le projet ou copiez les fichiers** dans un dossier de votre choix.
    ```bash
    git clone [URL_DE_VOTRE_FUTUR_REPO]
    cd LightningWash
    ```
2.  **Installez les dépendances** :
    ```bash
    pip install Flask
    ```
3.  **Configurez le script `server_pi.py`** :
    * Modifiez la variable `SECRET_KEY` pour y mettre une chaîne de caractères longue et aléatoire.
    * Ajustez les numéros des broches `RELAY_PIN` et `MAINTENANCE_SWITCH_PIN` pour qu'ils correspondent à votre branchement sur le Raspberry Pi.

4.  **(Pour la simulation uniquement)** Créez les fichiers de simulation à la racine du projet :
    * `mock_gpio.py` : (Copiez le code du simulateur GPIO).
    * `external_status.txt` : Créez ce fichier et écrivez-y `OFF`.

---

## Lancement du Serveur

Pour démarrer le serveur, exécutez la commande suivante dans votre terminal :
```bash
python server_pi.py
```
## Tester les requête API avec :

/start-wash
```bash
curl -X POST -H "Content-Type: application/json" -d "{\"secret\": \"VOTRE_SECRET_SUPER_UNIQUE_ICI\", \"duration\": 650}" http://localhost:5000/start-wash
```
/stop-wash
```bash
curl -X POST -H "Content-Type: application/json"  -d "{\"secret\": \"VOTRE_SECRET_SUPER_UNIQUE_ICI\"}" http://localhost:5000/stop-wash
```
/status
```bash
curl -X GET -H "Content-Type: application/json"  -d "{\"secret\": \"VOTRE_SECRET_SUPER_UNIQUE_ICI\"}" http://localhost:5000/status
```
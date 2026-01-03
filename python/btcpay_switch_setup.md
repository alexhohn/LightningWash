# Configuration du Bitcoin Switch Plugin pour LightningWash

Ce document explique comment configurer le plugin Bitcoin Switch de BTCPay Server pour contrôler votre LightningWash via WebSocket.

## Qu'est-ce que le Bitcoin Switch Plugin?

Le plugin Bitcoin Switch est une extension pour BTCPay Server qui permet de contrôler des appareils connectés à des broches GPIO (comme sur un Raspberry Pi) directement depuis BTCPay Server. Lorsqu'un paiement est reçu, BTCPay Server envoie un signal via WebSocket pour activer une broche GPIO pendant une durée spécifiée.

## Avantages par rapport à l'intégration Webhook

- **Configuration plus simple** : Pas besoin de configurer des webhooks ou de gérer des signatures
- **Interface utilisateur intégrée** : Configuration directement dans l'interface BTCPay Server
- **Communication en temps réel** : Utilisation de WebSockets pour une notification immédiate des paiements

## Prérequis

1. Un serveur BTCPay Server fonctionnel
2. Accès administrateur à votre BTCPay Server
3. Une application Point of Sale (POS) configurée dans BTCPay Server

## Installation du Plugin Bitcoin Switch

1. Connectez-vous à votre BTCPay Server en tant qu'administrateur
2. Accédez à la page "Plugins" dans le menu de navigation
3. Recherchez "Bitcoin Switch" dans la liste des plugins disponibles
4. Cliquez sur "Installer" sous le plugin "Bitcoin Switch"
5. Redémarrez votre BTCPay Server lorsque vous y êtes invité

## Configuration du Plugin

### Configuration de l'article dans le Point of Sale

1. Accédez à votre application Point of Sale (POS)
2. Cliquez sur "Paramètres" pour configurer votre application POS
3. Cliquez sur "Modifier" sur l'article que vous souhaitez utiliser pour activer le lavage
4. Dans les paramètres de l'article, vous verrez une nouvelle section "Bitcoin Switch"
5. Configurez les paramètres suivants:
   - **GPIO Pin**: Entrez `17` (le numéro de la broche GPIO connectée au relais de votre LightningWash)
   - **Duration**: Entrez la durée d'activation en secondes (par exemple, `60` pour un lavage d'une minute)
6. Enregistrez les modifications

### Configuration de l'affichage

Pour permettre aux clients de scanner un code QR LNURL spécifique à chaque article:

1. Dans les paramètres de votre application POS, sélectionnez "Print Display" comme style d'affichage
2. Enregistrez les modifications

## Configuration du Client WebSocket

Le client WebSocket est déjà intégré dans LightningWash. Vous devez simplement configurer l'URL WebSocket:

1. Déterminez l'URL WebSocket de votre BTCPay Server:
   - L'URL suit ce format: `wss://votre-btcpay-server.com/apps/APP_ID/pos/bitcoinswitch`
   - Remplacez `votre-btcpay-server.com` par le domaine de votre BTCPay Server
   - Remplacez `APP_ID` par l'identifiant de votre application POS (visible dans l'URL lorsque vous consultez votre application POS)

2. Configurez l'URL dans LightningWash en définissant la variable d'environnement:
   ```bash
   export BTCPAY_WEBSOCKET_URL="wss://votre-btcpay-server.com/apps/APP_ID/pos/bitcoinswitch"
   ```

## Démarrage de LightningWash avec l'intégration Bitcoin Switch

Vous pouvez démarrer LightningWash avec l'intégration Bitcoin Switch de deux façons:

### Option 1: Utiliser le script launcher

```bash
# Activer uniquement l'intégration Bitcoin Switch
python python/lightning_wash.py --bitcoinswitch

# Activer à la fois l'intégration webhook et Bitcoin Switch
python python/lightning_wash.py --all
```

### Option 2: Configurer via des variables d'environnement

```bash
# Activer l'intégration Bitcoin Switch
export ENABLE_BITCOINSWITCH_INTEGRATION="true"

# Désactiver l'intégration webhook si vous le souhaitez
export ENABLE_WEBHOOK_INTEGRATION="false"

# Démarrer LightningWash
python python/lightning_wash.py
```

## Test de l'intégration

### Test avec BTCPay Server

1. Démarrez LightningWash avec l'intégration Bitcoin Switch activée
2. Accédez à votre application Point of Sale dans BTCPay Server
3. Sélectionnez l'article configuré pour le lavage
4. Effectuez un paiement
5. Une fois le paiement confirmé, BTCPay Server enverra un signal via WebSocket à LightningWash
6. LightningWash activera le relais pendant la durée configurée

### Test sans BTCPay Server

Un script de test est fourni pour simuler des messages WebSocket de BTCPay Server sans avoir besoin d'une instance réelle :

```bash
# Test avec les paramètres par défaut (pin 17, durée 60 secondes)
python python/test_btcpay_switch.py

# Test avec des paramètres personnalisés
python python/test_btcpay_switch.py --pin 17 --duration 120

# Test avec une URL WebSocket personnalisée
python python/test_btcpay_switch.py --url ws://localhost:5000/btcpay-switch
```

Ce script est utile pour tester l'intégration Bitcoin Switch sans avoir à configurer un BTCPay Server complet.

## Dépannage

### Le client WebSocket ne se connecte pas

- Vérifiez que l'URL WebSocket est correcte
- Assurez-vous que votre BTCPay Server est accessible depuis le Raspberry Pi
- Vérifiez les journaux dans `btcpay_switch.log` pour plus de détails

### Le lavage ne démarre pas après un paiement

- Vérifiez que le numéro de broche GPIO configuré dans BTCPay Server correspond à la broche utilisée par LightningWash
- Assurez-vous que le client WebSocket est bien connecté (vérifiez les journaux)
- Vérifiez que le paiement est bien marqué comme "Settled" dans BTCPay Server

## Utilisation des deux méthodes d'intégration

LightningWash prend en charge à la fois l'intégration webhook et l'intégration Bitcoin Switch. Vous pouvez:

- Utiliser uniquement les webhooks
- Utiliser uniquement Bitcoin Switch
- Utiliser les deux méthodes simultanément pour plus de flexibilité

Pour configurer les deux méthodes, consultez à la fois ce document et `btcpay_webhook_setup.md`.

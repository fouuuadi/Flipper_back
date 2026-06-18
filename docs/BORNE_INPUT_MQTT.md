# Contrat MQTT — entrées physiques de la borne (boutons / plunger)

Frontière entre le **firmware ESP32** (lecture des GPIO) et le **backend**. Le
firmware reste agnostique du jeu : il publie des événements bruts (« le bouton
`L1` est pressé »). Le backend porte le mapping bouton → action (cf.
`app/usecase/handle_borne_input_usecase.py`).

> Source de vérité de ce contrat : ce fichier. Le miroir côté front est
> `Flipper_front/src/services/matchSync/protocol.ts` (`control:flipper` /
> `control:plunger`).

## Broker & abonnement

- Le firmware **publie** et le backend **s'abonne** au **même broker MQTT**
  (`MQTT_BROKER_HOST` / `MQTT_BROKER_PORT`).
- Filtre d'abonnement backend : `MQTT_BORNE_INPUT_TOPIC_FILTER`, valeur
  recommandée **`pinball/+/input/#`** (`+` = identifiant du device, `#` =
  `button` / `plunger`).

## Topics publiés par le firmware

| Topic | Payload | Sens |
|---|---|---|
| `pinball/<device>/input/button` | `{"id": "<id>", "state": 0\|1, "ts": <ms>}` | bouton pressé (`1`) / relâché (`0`) |
| `pinball/<device>/input/plunger` | `{"state": 0\|1, "ts": <ms>}` | lanceur chargé (`1`) / relâché (`0`) |

`<device>` est l'identifiant du device (ex. `esp32-test`). Pas de `sessionId`
dans le payload : c'est le backend qui sait, via la borne, quelle phase est
active.

## IDs de boutons et mapping (côté backend)

| `id` | GPIO | `control:nav` relayé | Rôle (orienté côté front) |
|---|---|---|---|
| `L1` | 4 | — (`control:flipper`) | Flipper **gauche** |
| `R1` | 13 | — (`control:flipper`) | Flipper **droit** |
| `L2` | 16 | `left` | Curseur **gauche** (menu / roulette) |
| `R2` | 25 | `right` | Curseur **droite** |
| `top` | 17 (vert) | `confirm` | **Valider** |
| `bottom` | 19 (rouge) | `back` | **Retour** |
| `middle` | 18 (jaune) | `help` | Écran **contrôles** |
| `under_plunger` | 33 | — | *(réservé)* |
| plunger | 32 | — (`control:plunger`) | **Lanceur** |

## Événements relayés au front (bus borne WS)

Toutes les entrées physiques sont **relayées telles quelles** aux 3 écrans ; le
backend ne décide pas de l'action (le front connaît l'écran courant / le
curseur) :

```json
{ "type": "control:flipper", "side": "left|right", "action": "press|release" }
{ "type": "control:plunger", "action": "charge|release" }
{ "type": "control:nav", "button": "confirm|back|left|right|help" }
```

Le front oriente `control:nav` selon l'écran (splash → `PRESS_A`, déplacement de
curseur dans le menu, roulette d'identification…) puis renvoie l'intent final
que le backend applique → `nav:state` (inchangé).

## ⚠️ À corriger côté firmware

1. **press/release** : binder `onPress → state 1` **et** `onRelease → state 0`
   (et non `onPress` deux fois). Sans relâché, un flipper ne peut pas être
   maintenu levé.
2. **plunger** : envoyer le `state` réel (`1` à l'appui, `0` au relâché), pas
   une valeur codée en dur.
3. **broker + device** : ne pas coder en dur le host du broker ni le `device` —
   les rendre configurables et convenir d'une valeur partagée avec le backend.

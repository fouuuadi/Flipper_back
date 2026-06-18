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

| `id` | GPIO | Rôle |
|---|---|---|
| `L1` | 4 | Flipper **gauche** (press/release) |
| `R1` | 13 | Flipper **droit** (press/release) |
| `L2` | 16 | Navigation **gauche** *(menu à curseur — à venir)* |
| `R2` | 25 | Navigation **droite** *(menu à curseur — à venir)* |
| `top` | 17 (vert) | **Valider / Start** (résolu selon l'état) |
| `bottom` | 19 (rouge) | **Retour** ; en jeu → **pause** |
| `middle` | 18 (jaune) | Secondaire *(réservé)* |
| `under_plunger` | 33 | *(réservé)* |
| plunger | 32 | **Lanceur** |

`top` (CONFIRM) et `bottom` (BACK) sont résolus en action concrète selon la
phase de navigation courante (`splash`→`PRESS_A`, `menu`→`START_GAME`,
`game_over`→`REPLAY`, etc.).

## Événements relayés au front (bus borne WS)

Les flippers et le plunger sont rebroadcastés tels quels aux 3 écrans :

```json
{ "type": "control:flipper", "side": "left|right", "action": "press|release" }
{ "type": "control:plunger", "action": "charge|release" }
```

La navigation, elle, passe par la machine d'état borne et ressort en
`nav:state` (inchangé).

## ⚠️ À corriger côté firmware

1. **press/release** : binder `onPress → state 1` **et** `onRelease → state 0`
   (et non `onPress` deux fois). Sans relâché, un flipper ne peut pas être
   maintenu levé.
2. **plunger** : envoyer le `state` réel (`1` à l'appui, `0` au relâché), pas
   une valeur codée en dur.
3. **broker + device** : ne pas coder en dur le host du broker ni le `device` —
   les rendre configurables et convenir d'une valeur partagée avec le backend.

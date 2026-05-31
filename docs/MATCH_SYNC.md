# MATCH_SYNC — Synchronisation des écrans front via WS

> Protocole serveur → clients pour piloter les 3 apps front (playfield, backglass, DMD) **en même temps** pendant une partie.
>
> Côté front, la doc miroir est dans `Flipper_front/docs/match-sync-architecture.md`.

---

## Principe

Les 3 apps front sont **3 process JS isolés** (3 services Docker, ports distincts). Pour qu'un événement comme "pause" s'affiche au même moment sur les 3 écrans, **le back devient source de vérité** pendant la durée de la partie.

- Le front envoie des **intentions** (`cmd:*`) via le WS existant
- Le back applique la transition côté `SessionStatus` (Redis)
- Le back **broadcast l'état nouveau** à tous les clients connectés à la session

```
[playfield] --cmd:pause-->  [back]
                            [back] valide + applique sur la session Redis
                            [back] broadcast match:state paused
                                ↓             ↓             ↓
                            [playfield] [backglass]   [dmd]
```

Pour la **reprise**, le flux est identique mais avec un countdown intercalé entre `PAUSED` et `PLAYING` :

```
[playfield] --cmd:resume--> [back]
                            [back] PAUSED → READY
                            [back] broadcast match:state ready
                            [back] StartCountdownUseCase (background task)
                              tick 3 → tick 2 → tick 1 → tick 0 (1s entre chaque)
                            [back] READY → PLAYING
                            [back] broadcast match:state playing
                                ↓             ↓             ↓
                            [playfield] [backglass]   [dmd]
```

**Hors-partie** (splash, menu, identification, leaderboard côté front), aucune sync n'est nécessaire — chaque app navigue de son côté. Voir la doc front pour la frontière exacte.

---

## Ce qui existe déjà côté back

| Aspect | État actuel |
|---|---|
| `Session.status` (Redis) | `WAITING` / `READY` / `PLAYING` / `OVER` — déclaré dans `app/domain/session.py` |
| Transitions actuelles | HTTP : `POST /sessions` → `WAITING`, `POST /sessions/{id}/ready` → `READY`<br>MQTT : `flipper/game/over` → `OVER` (cf. `handle_mqtt_event_usecase.py:103`) |
| Broadcast WS | `SessionHubManager.broadcast_to_session(session_id, message)` — déjà utilisé pour `score:update`, `ball:lost`, `game:over` |
| Réception WS | **Aucune** — le handler actuel `app/transport/ws/handler.py` lit les messages entrants mais les ignore (cf. ligne 58, 78) |

Le travail à faire est donc d'**étendre** ce qui existe, pas de tout réécrire.

---

## Extensions à livrer

### 1. Ajouter `PAUSED` à `SessionStatus`

```python
class SessionStatus(str, Enum):
    WAITING = "waiting"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"   # 🆕 entre PLAYING et OVER
    OVER = "over"
```

Transitions autorisées (à valider au cas par cas dans les use cases) :

| Depuis | Via | Vers |
|---|---|---|
| `WAITING` | `POST /sessions/{id}/ready` | `READY` |
| `READY` | démarrage countdown (cf. §4) | `PLAYING` |
| `PLAYING` | `cmd:pause` (WS) ou MQTT `flipper/pause` | `PAUSED` |
| `PAUSED` | `cmd:resume` (WS) — étape 1/2 | `READY` |
| `READY` (après `cmd:resume`) | fin de countdown | `PLAYING` |
| `PLAYING` ou `PAUSED` | `cmd:abandon` (WS) | `OVER` |
| `PLAYING` | MQTT `flipper/game/over` | `OVER` |

> ℹ️ Depuis l'issue #111, `cmd:resume` ne passe **plus** directement de `PAUSED` à `PLAYING`. Le use case intercale un retour à `READY` + countdown 3-2-1-GO (identique au démarrage initial), pour une UX de reprise non-brutale côté front. Voir §4 pour le mécanisme partagé.

Une transition non autorisée doit être ignorée silencieusement (log warning, pas d'erreur HTTP).

### 2. Messages WS server → client à ajouter

Émis sur le `SessionHub` correspondant à la session :

```jsonc
// Statut courant — broadcasté à chaque transition côté back
{
  "type": "match:state",
  "status": "waiting" | "ready" | "playing" | "paused" | "over",
  "sessionId": "<uuid>"
}

// Countdown pré-partie (avant le passage effectif à PLAYING)
{ "type": "countdown:tick", "value": 3 | 2 | 1 | 0 }
```

Les messages existants (`score:update`, `ball:lost`, `game:over`) restent **inchangés**.

### 3. Messages WS client → server (nouveaux)

Le handler doit lire les messages entrants et router selon le `type` :

```jsonc
{ "type": "cmd:pause" }
{ "type": "cmd:resume" }
{ "type": "cmd:abandon" }
```

Comportement attendu :

- Récupérer le `session_id` depuis le query param du WS (déjà disponible)
- Charger la session depuis Redis
- Si la transition est autorisée pour le `SessionStatus` courant, appliquer + broadcast `match:state`
- Sinon, log warning et ne rien faire

### 4. Countdown 3-2-1-GO (initial **et** reprise)

Le même `StartCountdownUseCase` est partagé entre deux déclencheurs :

- **Initial** : `POST /sessions/{id}/ready` (le joueur valide son pseudo et part en partie)
- **Reprise** : `cmd:resume` reçu sur le WS (le joueur clique "reprendre" pendant une pause)

Dans les deux cas, la session est posée à `READY`, le countdown asyncio démarre en fire-and-forget, et :

1. Broadcast `countdown:tick` avec `value: 3`
2. Attend 1 seconde
3. Broadcast `value: 2`
4. Attend 1 seconde
5. Broadcast `value: 1`
6. Attend 1 seconde
7. Broadcast `value: 0`
8. Bascule `Session.status` à `PLAYING` + broadcast `match:state: playing`

**Pendant le countdown** (que ce soit l'initial ou la reprise), les events MQTT score/ball pour cette session sont **ignorés** — la partie n'est pas encore active. Le gating est centralisé dans `HandleMqttEventUseCase` qui vérifie `session.status == PLAYING` avant d'appliquer score/lives. Aucun cas particulier à gérer pour la reprise : le passage à `READY` suffit à activer le drop côté MQTT.

> Côté front, le binding `countdown:tick` est déjà câblé sur les 3 apps (validé bout en bout dans front PR #101). La reprise réutilise le même handler — aucune modification front nécessaire.

### 5. Émettre `match:state` aux transitions existantes

Aujourd'hui seul `game:over` est broadcasté en fin de partie. Ajouter :

- À la création de la session (`POST /sessions`) : `match:state: waiting` — **optionnel** car le client vient de créer la session, il connaît déjà l'état.
- À `POST /sessions/{id}/ready` : `match:state: ready` (puis countdown démarre)
- Post-countdown : `match:state: playing`
- MQTT `flipper/game/over` : conserve `game:over` + ajoute `match:state: over` (l'un signale la fin de jeu, l'autre la fin de cycle de session)

Pour le front, `game:over` reste l'event "score final", `match:state: over` est ce qui pilote la transition d'écran.

---

## Architecture des use cases (proposition)

```
app/usecase/
├── pause_session_usecase.py       🆕 transition PLAYING → PAUSED
├── resume_session_usecase.py      🆕 transition PAUSED → PLAYING
├── abandon_session_usecase.py     🆕 transition PLAYING|PAUSED → OVER
└── start_countdown_usecase.py     🆕 démarre l'asyncio task de countdown
```

Tous suivent le pattern existant (Clean Archi, `import-linter`).

Le **handler WS** (`app/transport/ws/handler.py`) reçoit les `cmd:*` et appelle le bon use case via `app/di.py`.

---

## Format d'erreur

Côté WS, on ne propage **pas** d'erreur structurée pour les commandes invalides : silencieux côté serveur, log warning. Si un client envoie une commande absurde (genre `cmd:pause` alors qu'on est en `WAITING`), c'est un bug du front, pas une situation à signaler.

Pour les erreurs **structurelles** (session inexistante, payload mal formé), le WS se ferme avec un code 1002 ("protocol error") et un reason court.

---

## Découpage en issues back

### back#A — `SessionStatus.PAUSED` + `cmd:*` côté WS ✅ (issue #105)
- ✅ Ajout de l'enum
- ✅ 3 use cases (pause / resume / abandon)
- ✅ Handler WS lit les messages entrants, route vers use case
- ✅ Broadcast `match:state` à chaque transition
- ✅ Tests : transitions autorisées / interdites, idempotence, broadcast effectif

### back#B — Countdown pré-partie ✅ (issue #106)
- ✅ `StartCountdownUseCase` (asyncio task lancé sur `ready_up` via callback `on_ready`)
- ✅ `HandleMqttEventUseCase` ignore score/lives si `status != PLAYING`
- ✅ Tests : sleep injectable (pas d'attente réelle), gating MQTT pendant countdown, edge case "cmd:abandon en cours de countdown"

### back#C — Émission systématique de `match:state` aux transitions existantes ✅ (issue #104)
- ✅ `ReadyUpUseCase` broadcast `match:state: ready`
- ✅ `HandleMqttEventUseCase` broadcast `match:state: over` en plus de `game:over` sur `flipper/game/over`
- ✅ Tests : présence du message dans le hub à chaque transition

### back#D — Countdown 3-2-1-GO sur `cmd:resume` ✅ (issue #111)
- ✅ `ResumeSessionUseCase` orchestre `PAUSED → READY` + lance le countdown partagé
- ✅ `StartCountdownUseCase` réutilisé tel quel (même sleep injectable, même garde `status == READY` avant la bascule finale)
- ✅ `HandleMqttEventUseCase` continue de gater sur `status == PLAYING` (aucun cas particulier à ajouter pour la reprise)
- ✅ Tests : séquence complète `match:state: ready → 4 ticks → match:state: playing`, drop MQTT pendant la phase `READY` du resume, no-op silencieux sur `WAITING` / `PLAYING` / `OVER`

### back#E (optionnel, plus tard)
- Topics MQTT `flipper/pause` et `flipper/resume` pour piloter les transitions depuis le hardware (gros bouton physique pause sur la borne)

---

## Tests d'acceptation côté back

- [ ] `cmd:pause` reçu pendant `PLAYING` → session passe à `PAUSED`, broadcast à tous les clients du hub
- [ ] `cmd:pause` reçu pendant `WAITING` → ignoré, log warning, hub silent
- [ ] `cmd:resume` reçu pendant `PAUSED` → session passe à `PLAYING`, broadcast
- [ ] `cmd:abandon` reçu pendant `PLAYING` ou `PAUSED` → session passe à `OVER`, broadcast `match:state: over` (note : `game:over` n'est pas émis car ce n'est pas un game over "naturel")
- [ ] `POST /sessions/{id}/ready` déclenche un countdown 3-2-1-0 puis transition vers `PLAYING`
- [ ] MQTT `flipper/bumper/hit` pendant le countdown est silencieusement ignoré (pas d'update score)
- [ ] 2 clients WS sur la même session reçoivent les mêmes messages dans le même ordre

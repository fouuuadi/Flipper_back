# Workflow d'une partie Flipper — vue end-to-end

> Doc vivante. À mettre à jour dans la même PR qui modifie le flow (cf. `feedback_workflow_doc` en mémoire).
>
> Décrit le cycle de vie complet d'une partie, des composants impliqués, et de leur séquence — depuis l'enregistrement du pseudo jusqu'à la persistance en DB.

---

## Vue globale

```
                            ┌─────────────────────────────┐
                            │   Flipper hardware (IoT)    │
                            │   bumpers, capteurs, ...    │
                            └──────────────┬──────────────┘
                                           │ publish
                                           ▼
                            ┌─────────────────────────────┐
                            │  MQTT broker (Mosquitto)    │
                            │  flipper/#                  │
                            └──────────────┬──────────────┘
                                           │ subscribe
                                           ▼
[Client (web/app)]                ┌────────────────────┐
       │                          │  AioMqttGateway    │
       │                          └─────────┬──────────┘
       │  POST /sessions                    │ MqttEvent
       │  POST /sessions/{id}/ready         ▼
       ├─────────────────────────► ┌────────────────────────────┐
       │                          │  HandleMqttEventUseCase    │
       │                          │  1. Mute Session (Redis)   │
       │                          │  2. Push to EventBuffer    │ ──► Redis List
       │                          │     (Redis List)           │     events:{sid}
       │                          │  3. Broadcast WS           │
       │                          └─────────┬──────────────────┘
       │  WS /ws?session_id=X               │ broadcast
       │◄────────────────────────► ┌────────────────────────────┐
       │  score:update             │  SessionHubManager         │
       │  ball:lost                │  (one hub per session_id)  │
       │  game:over                └────────────────────────────┘
       │
       │  POST /scores
       └─────────────────────────► ┌────────────────────────────┐
                                  │ FinishAndPersistUseCase    │
                                  │ 1. Read Redis Session      │
                                  │ 2. Read EventBuffer        │
                                  │ 3. Atomic DB transaction:  │
                                  │    INSERT Player (upsert)  │
                                  │    INSERT Game             │
                                  │    INSERT GameEvents (bulk)│
                                  │ 4. DELETE Redis session    │
                                  │ 5. DELETE event buffer     │
                                  └─────────┬──────────────────┘
                                            ▼
                                  ┌────────────────────────────┐
                                  │  MySQL (persistance finale)│
                                  │  players / games /         │
                                  │  game_events               │
                                  └────────────────────────────┘
```

---

## Phases détaillées

### Phase 1 — Enregistrement (HTTP pur, avant la partie)

#### `POST /sessions`
- **Reçoit** : `{ pseudo: "ABC", mode: "solo" | "1v1", room_code?: "..." }`
- **Génère** : `session_id` (UUID hex) + formate le pseudo en `ABC#4521` (suffixe 4 chiffres aléatoires)
- **Crée** : une session Redis (`Hash session:{session_id}`) avec TTL **30 min sliding** (rafraîchi à chaque read/update)
- **Retourne** : `{ session_id, pseudo, status: "waiting", mode, room_code }`
- ⚠️ **Pas d'écriture en DB à ce stade**

Champs Redis Hash :
```
session_id, pseudo, score (=0), lives (=3), combo (=0),
status (=waiting), room_code, mode (=solo|1v1), created_at
```

#### `POST /sessions/{session_id}/ready`
- **Effet** : passe le statut Redis à `ready`
- **Retourne** : `{ session_id, status: "ready" }`
- ⚠️ La logique "tous prêts → broadcast `game:start`" pour le 1v1 viendra plus tard (#59 matchmaking)

---

### Phase 2 — Connexion WebSocket (handshake)

#### `WS /ws?session_id=X`
- Valide que la session existe dans Redis (sinon close 1000)
- Ajoute le client au `SessionHub(session_id)` (broadcast scoped à cette session uniquement)
- Maintient la connexion ouverte pendant toute la partie
- À la déconnexion → retire le client du hub

Variante héritée (toujours supportée) : `WS /ws?room_code=Y` pour le broadcast room-scoped (flow rooms d'origine). Les deux query params sont **mutuellement exclusifs**.

---

### Phase 3 — Pendant la partie (boucle MQTT → Redis → WS)

Le hardware (flipper physique ou simulateur) publie des events JSON sur le broker MQTT. Le backend est abonné à `flipper/#`.

**Topics gérés** :

| Topic | Payload | Effet Redis | Event WS broadcasté |
|---|---|---|---|
| `flipper/bumper/hit` | `{bumperId, points, sessionId}` | `score += points`, `combo++` | `score:update {score, combo, bumperId}` |
| `flipper/bonus` | `{type, points, sessionId}` | `score += points` | `score:update {score, combo, bonusType}` |
| `flipper/ball/lost` | `{sessionId}` | `lives--` (min 0), `combo = 0` | `ball:lost {livesRemaining}` |
| `flipper/game/over` | `{sessionId}` | `status = OVER` | `game:over {finalScore}` |

**Pour chaque event reçu, `HandleMqttEventUseCase`** :
1. Charge la session depuis Redis (`session:{session_id}`)
2. Mute la session selon le topic (score, lives, combo, status)
3. Persiste la session mise à jour (`UPDATE session:{session_id}`)
4. **Push l'event brut** dans la Redis List `events:{session_id}` *(EventBuffer — accumulation pour le flush final)*
5. Broadcast le message WS au `SessionHub(session_id)` correspondant

Edge cases :
- Topic inconnu → log + drop, session intacte, pas de broadcast
- Payload non-JSON ou non-object → drop côté gateway, n'arrive même pas au use case
- `sessionId` manquant ou session inconnue dans Redis → log warning + drop

---

### Phase 4 — Fin de partie (HTTP, **unique moment d'écriture DB**)

#### `POST /scores`
- **Reçoit** : `{ sessionId }`
- **Lit** :
  - Session depuis Redis (score final, pseudo, mode, started_at)
  - Buffer d'events depuis Redis List `events:{session_id}`
- **Transaction MySQL atomique** (rollback complet si une étape échoue) :
  1. `INSERT INTO players (pseudo)` avec upsert (`ON DUPLICATE KEY` → récupère l'`id` existant)
  2. `INSERT INTO games (player_id, mode, score, started_at, finished_at, status=FINISHED)`
  3. `INSERT INTO game_events (game_id, type, points, occured_at) VALUES (...)` en batch
- **Cleanup Redis** : DELETE session + DELETE event buffer (après commit DB OK)
- **Retourne** : `{ ok, finalScore, playerId, gameId, eventCount }`

Cas spéciaux :
- Session introuvable dans Redis → 404
- Aucun event dans le buffer (ex: partie courte sans MQTT) → Game créé quand même, `game_events` reste vide, pas d'erreur
- Si la transaction DB échoue → Redis n'est PAS nettoyé, le client peut retenter

---

## Composants impliqués (par couche)

| Couche | Composant | Rôle |
|---|---|---|
| **Domain** | `Session`, `Player`, `Game`, `GameEvent`, `Room`, `Match` | Entités Pydantic |
| **Domain Ports** | `SessionStore` | CRUD session Redis (Hash) |
| | `EventBuffer` | Push/read events MQTT (Redis List) |
| | `GameRepository`, `PlayerRepository`, `GameEventRepository`, `RoomRepository` | CRUD DB |
| | `MqttGateway` | Subscribe broker + dispatch event |
| | `SessionEventBroadcaster` | Broadcast WS scoped session |
| **Infrastructure Redis** | `RedisSessionStore` | Hash + sliding TTL 30min |
| | `RedisEventBuffer` | List + sliding TTL 30min |
| **Infrastructure DB** | `MysqlPlayerRepository`, `MysqlGameRepository`, ... | aiomysql + SQL brut |
| **Infrastructure MQTT** | `AioMqttGateway` | aiomqtt async client + consumer task |
| **Infrastructure WS** | `SessionHubManager` | 1 `SessionHub` par session_id |
| | `HubManager` (legacy room) | 1 `RoomHub` par room_code |
| **Use cases** | `CreateSessionUseCase`, `ReadyUpUseCase` | Avant la partie |
| | `HandleMqttEventUseCase` | Pendant la partie |
| | `FinishAndPersistUseCase` | Fin de partie |
| **Transport HTTP** | `sessions.py`, `scores.py`, `rooms.py`, `games.py` | Endpoints REST |
| **Transport WS** | `handler.py` | `/ws` (session_id XOR room_code) |

---

## État du plan de migration

| Étape | Statut | PR |
|---|---|---|
| 1. Redis sessions | ✅ Mergé | #91 |
| 2. Sessions endpoints HTTP | ✅ Mergé | #92 |
| 3. MQTT broker bridge | ✅ Mergé | #93 |
| 4. Bridge MQTT → Redis → WS | ✅ Mergé | #94 |
| 5. POST /scores + EventBuffer | 🚧 En cours | feat/post-scores-flush |
| 6. Migration MySQL → PostgreSQL | 📌 À faire | #89 |

---

## Comment tester le flow end-to-end localement

```bash
# 1. Démarrer la stack
docker compose up -d db redis mqtt
DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=flipper_user DB_PASSWORD=flipper_password \
  DB_NAME=flipper REDIS_URL=redis://127.0.0.1:6379 \
  MQTT_BROKER_HOST=127.0.0.1 MQTT_BROKER_PORT=1883 \
  python3 -m app.main

# 2. Créer une session
curl -X POST localhost:8080/sessions \
  -H 'Content-Type: application/json' \
  -d '{"pseudo":"ABC","mode":"solo"}'
# → { "session_id": "XYZ...", "pseudo": "ABC#1234", "status": "waiting", "mode": "solo" }

# 3. Ouvrir un WebSocket dans un autre terminal
wscat -c "ws://localhost:8080/ws?session_id=XYZ..."

# 4. Publier des events MQTT (simule le hardware)
docker exec flipper_mqtt mosquitto_pub -t flipper/bumper/hit \
  -m '{"bumperId":1,"points":100,"sessionId":"XYZ..."}'
docker exec flipper_mqtt mosquitto_pub -t flipper/ball/lost \
  -m '{"sessionId":"XYZ..."}'
docker exec flipper_mqtt mosquitto_pub -t flipper/game/over \
  -m '{"sessionId":"XYZ..."}'

# → wscat affiche score:update, ball:lost, game:over

# 5. Flush en DB
curl -X POST localhost:8080/scores \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"XYZ..."}'
# → { "ok": true, "finalScore": 100, "playerId": 1, "gameId": 1, "eventCount": 3 }

# 6. Vérifier en DB
docker exec flipper_db mysql -uflipper_user -pflipper_password flipper \
  -e "SELECT * FROM games ORDER BY id DESC LIMIT 1;"
```

# API Reference — Flipper Backend

> Référence des endpoints **HTTP REST** et du protocole **WebSocket**.
> Payloads et codes tirés du code réel (`app/transport/`).
>
> Pour le **flux** dans lequel ces endpoints s'enchaînent, voir [`WORKFLOW.md`](./WORKFLOW.md).
> Pour le détail du protocole pause/resume/abandon, voir [`MATCH_SYNC.md`](./MATCH_SYNC.md).
> Pour la structure du code, voir [`ARCHITECTURE.md`](./ARCHITECTURE.md).

Base URL en local : `http://localhost:8080` (port `APP_PORT`, défaut `8080`).

---

## Conventions transverses

- **Format pseudo en entrée** : `^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$` (3 alphanum, hashtag optionnel). Normalisé côté serveur : uppercase + ajout de `#HETIC` si absent → format stocké `XXX#YYYYY`. Entrée non conforme → `422`.
- **Modes de jeu** (`GameMode`) : `solo` | `1v1`.
- **Erreurs métier** : les `DomainError` sont mappées en codes HTTP par `app/transport/http/error_handler.py`. Les erreurs de validation Pydantic (pattern, bornes) renvoient `422`.
- **Observabilité** : chaque réponse porte un header `X-Request-ID` (corrélation avec les logs JSON serveur).
- ⚠️ **Casse des champs** : `POST /scores` est le seul endpoint en **camelCase** (`sessionId`, `finalScore`…). Tout le reste est en **snake_case**.

---

## 1. Sessions — `/sessions`

Cycle de vie éphémère d'une partie (stocké en Redis, pas en DB). Cf. Phase 1 du `WORKFLOW.md`.

### `POST /sessions` → `201 Created`
Crée une session éphémère. **Aucune écriture DB.**

Requête :
```json
{ "pseudo": "ABC", "mode": "solo", "room_code": null }
```
| Champ | Type | Requis | Défaut |
|---|---|---|---|
| `pseudo` | string (pattern ci-dessus) | ✅ | — |
| `mode` | `solo` \| `1v1` | ❌ | `solo` |
| `room_code` | string \| null | ❌ | `null` |

Réponse :
```json
{ "session_id": "a1b2c3...", "pseudo": "ABC#HETIC", "status": "waiting", "mode": "solo", "room_code": null }
```
Codes : `201` · `422` (pseudo/mode invalide).

### `POST /sessions/{session_id}/ready` → `200 OK`
Passe la session à `ready` et déclenche le countdown pré-partie (3-2-1-0 broadcasté en WS, cf. `MATCH_SYNC.md`).

Réponse : `{ "session_id": "a1b2c3...", "status": "ready" }`
Codes : `200` · `404` (session inconnue).

---

## 2. Scores — `/scores`

### `POST /scores` → `200 OK`
**Unique moment d'écriture DB.** Lit la session + le buffer d'events en Redis, persiste Player+Game+GameEvents dans une transaction atomique, puis nettoie Redis. Cf. Phase 4 du `WORKFLOW.md`.

Requête (**camelCase**) :
```json
{ "sessionId": "a1b2c3..." }
```

Réponse (**camelCase**) :
```json
{
  "ok": true,
  "finalScore": 1200,
  "playerId": 42,
  "gameId": 87,
  "eventCount": 15,
  "improved": true,
  "previousBest": 900
}
```
- `improved` / `previousBest` : significatifs **uniquement en solo** (règle « best score wins »). En `1v1` → `null`.

Codes : `200` · `404` (session introuvable en Redis).

---

## 3. Players — `/players`

Gestion du profil joueur, indépendante du cycle d'une partie.

| Endpoint | Description | Succès | Erreurs |
|---|---|---|---|
| `POST /players` | **Idempotent** : crée le Player si absent, sinon renvoie l'existant. Body `{ "pseudo": "ABC" }`. | `200` | `422` |
| `GET /players/{player_id}` | Lookup par id. | `200` | `404` |
| `GET /players?pseudo=ABC` | Lookup par pseudo (normalisé). | `200` | `404`, `422` |
| `GET /players/{player_id}/games?mode=&limit=` | Historique des games **terminées**, DESC sur `finished_at`. `mode` optionnel, `limit ∈ [1,100]` (défaut `20`). | `200` (liste vide possible) | `404` |

`PlayerResponse` : `{ "id": 42, "pseudo": "ABC#HETIC", "created_at": "2026-..." }`

Historique (`GET /players/{id}/games`) :
```json
{
  "player_id": 42,
  "pseudo": "ABC#HETIC",
  "games": [
    { "game_id": 87, "mode": "solo", "score": 1200, "started_at": "...", "finished_at": "...", "is_best": true }
  ]
}
```
`is_best` : `true` uniquement pour la game solo au meilleur score du joueur.

---

## 4. Leaderboard — `/leaderboard`

### `GET /leaderboard?mode=&limit=` → `200 OK`
Top N des meilleurs scores, **une entrée par joueur** (`MAX(score)`), seules les games `finished` comptent.

| Param | Type | Défaut |
|---|---|---|
| `mode` | `solo` \| `1v1` \| absent (tous modes) | absent |
| `limit` | int `[1,100]` | `10` |

Réponse :
```json
{
  "mode": "solo",
  "limit": 10,
  "entries": [
    { "rank": 1, "player_id": 42, "pseudo": "ABC#HETIC", "score": 1200 }
  ]
}
```
`rank` calculé côté backend (1-based, DESC). Codes : `200` · `422` (mode/limit hors borne).

---

## 5. Rooms & Games (flow legacy)

> Flow d'origine pré-migration (écriture DB directe). Toujours en service, mais le flow
> nominal d'une partie passe désormais par `sessions` + `scores` + MQTT. À terme dépréciable.

### Rooms — `/rooms`
| Endpoint | Description | Succès | Erreurs |
|---|---|---|---|
| `POST /rooms` | Crée une room. Body `{ "mode": "solo" \| "1v1" }`. Réponse : `room_code`, `mode`, `status`, `created_at`. | `201` | `422` (mode invalide) |
| `POST /rooms/{code}/join` | Rejoint une room, renvoie ses games. | `200` | `404` (`RoomNotFoundError` via handler global) |
| `GET /rooms/list?status=` | Liste les rooms (filtre `status` optionnel). | `200` | — |

### Games — `/games`
| Endpoint | Description | Succès |
|---|---|---|
| `POST /games/start` | Démarre une partie (Player+Room+Game+Event en **une transaction**, via Unit of Work). Body `{ pseudo, mode, room_code }`. | `201` |
| `POST /games/{game_id}/events` | Ajoute un event à une game en cours. Body `{ type, points }`. Renvoie `new_score`. | `201` |
| `POST /games/{game_id}/finish` | Termine une game (`status=finished`, `finished_at`). | `200` |
| `GET /games/{game_id}` | État complet d'une game + ses events. | `200` |
| `GET /games/rooms/{code}/state` | État d'une room + toutes ses games et events. | `200` |
| `GET /games/list?status=` | Liste les games (filtre `status` optionnel). | `200` |

---

## 6. Health & root

| Endpoint | Méthodes | Réponse |
|---|---|---|
| `GET /` | GET | `{ "message": "Flipper backend running" }` |
| `/health` | GET, HEAD | `{ "status": "ok" }` |

---

## 7. WebSocket — `/ws`

### Connexion : `WS /ws?session_id=X` **XOR** `?room_code=Y`
Les deux query params sont **mutuellement exclusifs** (les deux ou aucun → close `1000`).

| Param | Mode | Sens |
|---|---|---|
| `session_id` | **session-scoped** | reçoit les events de la session ; le client peut **envoyer** des `cmd:*` |
| `room_code` | **room-scoped** (legacy) | reçoit tout ce qui est broadcasté pour la room ; **read-only** |

Fermetures (close code `1000`) : session/room introuvable, ou XOR violé.

### Messages **entrants** (client → serveur, session uniquement)
JSON `{ "type": "cmd:..." }`. Payload malformé ou type inconnu → log + drop silencieux.

| `type` | Effet | Use case |
|---|---|---|
| `cmd:pause` | `PLAYING → PAUSED` | `PauseSessionUseCase` |
| `cmd:resume` | `PAUSED → PLAYING` (+ countdown) | `ResumeSessionUseCase` |
| `cmd:abandon` | `PLAYING\|PAUSED → OVER` | `AbandonSessionUseCase` |

### Messages **sortants** (serveur → client, broadcast scoped session)
Émis par le bridge MQTT (`HandleMqttEventUseCase`) et par les use cases de cycle de vie :

| Event | Origine | Payload |
|---|---|---|
| `score:update` | MQTT `bumper/hit`, `bonus` | `{ score, combo, bumperId? \| bonusType? }` |
| `ball:lost` | MQTT `ball/lost` | `{ livesRemaining }` |
| `game:over` | MQTT `game/over` | `{ finalScore }` |
| `countdown` / `paused` / `resumed` / `abandoned` | cycle de vie (cf. `MATCH_SYNC.md`) | voir `MATCH_SYNC.md` |

> Détail exhaustif des payloads de cycle de vie (countdown 3-2-1-0, pause, resume, abandon) : [`MATCH_SYNC.md`](./MATCH_SYNC.md).

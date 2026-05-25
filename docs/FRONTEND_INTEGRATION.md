# Frontend Integration Guide — Flipper Backend

> Doc d'intégration destinée au repo `Flipper_front`. Tout ce qu'il faut pour brancher les écrans (`#75` → `#83`) sur l'API HTTP, le WebSocket et comprendre la chaîne MQTT.
>
> **Aucun code Python ici.** Que des schémas TypeScript et des descriptions consommables.

---

## 1. Vue d'ensemble

### URLs

| Environnement | Base HTTP | Base WebSocket |
|---|---|---|
| Dev local (Docker Compose) | `http://localhost:8080` | `ws://localhost:8080` |
| CI | `http://127.0.0.1:8080` | `ws://127.0.0.1:8080` |
| Prod | _non déployé_ | _non déployé_ |

### Authentification / Identification

**Pas d'auth.** Le backend ne gère ni JWT, ni cookie, ni header `Authorization`. L'identification se fait par :

- **HTTP** : le client passe `sessionId` (ou `playerId`) dans le body / query selon l'endpoint
- **WebSocket** : le client passe `?session_id=...` ou `?room_code=...` en query param à l'ouverture du socket

### Tracing

Chaque réponse HTTP porte un header **`X-Request-ID`** (UUID hex) — utile pour corréler logs serveur ↔ appels client. Le frontend devrait le logger en cas d'erreur.

### Format d'erreur (toutes les routes)

Toutes les erreurs (validation, domaine, conflit, 404, etc.) renvoient le même shape JSON :

```ts
interface ApiError {
  error: string;   // Nom de la classe d'erreur côté serveur (ex: "PlayerNotFoundError")
  detail: string;  // Message lisible (peut contenir des infos contextuelles)
}
```

| Code HTTP | Quand | Exemples `error` |
|---|---|---|
| `400` | Erreur domaine générique (`DomainError`) | `DomainError` |
| `404` | Ressource non trouvée | `PlayerNotFoundError`, `RoomNotFoundError`, `GameNotFoundError`, `SessionNotFoundError` |
| `409` | Conflit d'état | `PlayerAlreadyExistsError`, `GameAlreadyFinishedError`, `GameNotPlayableError` |
| `422` | Validation de format / contrainte | `InvalidPseudoError`, ou validation Pydantic (shape différent ci-dessous) |

> ⚠️ Les erreurs **422 Pydantic** (DTO invalide, champ requis manquant, regex non matchée) suivent le format standard FastAPI, pas le format `ApiError` :
> ```ts
> interface PydanticValidationError {
>   detail: Array<{
>     loc: (string | number)[];
>     msg: string;
>     type: string;
>     // ... autres champs Pydantic
>   }>;
> }
> ```
> Pour distinguer : si `detail` est un **array** → validation Pydantic ; si c'est une **string** → `ApiError` domain.

---

## 2. Flow type d'une partie

### Mode solo (de bout en bout)

```
┌─────────────────────────────────────────────────────────────────┐
│  État front: splash / menu                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼  user tape "ABC" (#75 identification)
                  ┌─────────────────────────┐
                  │ POST /sessions           │
                  │ { pseudo: "ABC",         │
                  │   mode: "solo" }         │
                  └────────┬────────────────┘
                           │ 201
                           ▼
                  { session_id: "abc123...",
                    pseudo: "ABC#HETIC",
                    status: "waiting" }
                              │
                              ▼  État front: identification → playing
                  ┌─────────────────────────┐
                  │ POST /sessions/         │
                  │      {sid}/ready        │
                  └────────┬────────────────┘
                           │ 200
                           ▼
                  { session_id, status: "ready" }
                              │
                              ▼  ouverture du WS
                  ┌─────────────────────────┐
                  │ WS /ws?session_id=...   │
                  │  (connexion maintenue)  │
                  └────────┬────────────────┘
                           │
                           │  Le flipper hardware publie sur MQTT
                           │  ↓ (le back relaie)
                           ▼
                  ┌─────────────────────────┐
                  │  Events WS reçus :      │
                  │  - score:update         │
                  │  - ball:lost            │
                  │  - game:over            │
                  └────────┬────────────────┘
                           │ (boucle pendant toute la partie)
                           │
                           │  game:over reçu → État front: gameOver
                           ▼  (#78 sauvegarde)
                  ┌─────────────────────────┐
                  │ POST /scores            │
                  │ { sessionId: "abc..." } │
                  └────────┬────────────────┘
                           │ 200
                           ▼
                  { ok, finalScore, playerId, gameId,
                    improved, previousBest }
                              │
                              ▼  Affichage résultat
                  ┌─────────────────────────┐
                  │ GET /leaderboard        │
                  │   ?mode=solo&limit=10   │   (#79 leaderboard)
                  └─────────────────────────┘
```

### Variante mode 1v1

🚧 **Le matchmaking 1v1 (issue #59) n'est pas implémenté**. Aujourd'hui le mode `"1v1"` est accepté par `POST /sessions` mais aucune logique d'appariement automatique n'existe.

Workaround temporaire pour tester un duel :
- Joueur A : `POST /sessions { pseudo: "ABC", mode: "1v1", room_code: "ROOM01" }`
- Joueur B : `POST /sessions { pseudo: "XYZ", mode: "1v1", room_code: "ROOM01" }` (même `room_code`)
- Chacun ouvre son WS avec son `session_id` propre
- Pas de broadcast `game:start` synchronisé côté backend pour l'instant

### Pause / Resume / Abandon

🚧 **Pas d'endpoint dédié.** Côté backend, une session reste en Redis avec TTL 30 min sliding. Le front peut :
- **Pause** : interrompre la partie côté UI uniquement (état `paused`). La session Redis reste vivante.
- **Resume** : reprendre l'UI, le WS reste ouvert.
- **Abandon** : appeler `POST /scores` même si la partie n'est pas terminée naturellement (le score actuel sera persisté).

---

## 3. Mapping écran front → endpoints

### #75 — `identification` (saisie pseudo)

**Endpoints utilisés**
- `POST /sessions` — crée la session de jeu et normalise le pseudo (`"ABC"` → `"ABC#HETIC"`)
- `POST /sessions/{session_id}/ready` — flag la session prête juste avant d'ouvrir le WS

**Events WS**
- Aucun à ce stade

**Erreurs à gérer**
- `422` body invalide (pseudo ne matche pas `^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$`) → réafficher le champ avec une erreur "format invalide (3 caractères + optionnellement #5 caractères)"
- `404` (sur `/ready`) `SessionNotFoundError` → session expirée, repartir au début

**TODO côté back**
- Aucun pour cet écran — tout est en place.

### #76 — `menu` (entrée, lance la partie)

**Endpoints**
- `POST /sessions` (idem #75 si on entre directement par le menu)

**Events WS**
- Aucun

**TODO côté back**
- Aucun.

### #77 — `pause`

**Endpoints**
- Aucun appel côté back (la pause est UI-only pour l'instant)

**TODO côté back**
- Optionnel futur : `POST /sessions/{id}/pause` + `POST /sessions/{id}/resume`. Pas dans le scope actuel.

### #78 — `gameOver` (sauvegarde)

**Endpoints**
- `POST /scores` — flush atomique de la session Redis → DB

**Events WS**
- Déclenché en réaction à l'event WS `game:over` reçu (le frontend décide d'appeler `POST /scores` à ce moment-là)

**Erreurs à gérer**
- `404 SessionNotFoundError` → session expirée (TTL Redis dépassé). Possibilité côté UI : "score perdu, désolé"
- En succès : si `improved=true` afficher "🏆 nouveau record", si `improved=false` afficher `"Ton record reste {previousBest}"`, si `improved=null` (mode 1v1) afficher juste le score sans notion de record

**TODO côté back**
- Aucun.

### #79 — `leaderboard`

**Endpoints**
- `GET /leaderboard?mode=solo&limit=10` (ou `?mode=1v1`, ou sans `mode` pour tous modes confondus)
- `GET /players/{id}/games?mode=solo&limit=20` — historique d'un joueur (utile pour une vue "détails joueur" depuis le leaderboard)

**Events WS**
- Aucun

**Erreurs à gérer**
- `422` si `limit` est hors `[1, 100]` ou si `mode` ne fait pas partie de `"solo" | "1v1"`

**TODO côté back**
- Aucun.

### #81 — `leaderboardStore`

Couche d'accès qui doit implémenter une interface unique avec deux backends interchangeables :

- **localStorage** (pour dev offline / tests)
- **HTTP** (`GET /leaderboard?...`, `GET /players/{id}/games?...`)

Le type minimal d'une entrée leaderboard côté front :

```ts
interface LeaderboardEntry {
  rank: number;
  player_id: number;
  pseudo: string;
  score: number;
}
```

### #82 — `backglass` et #83 — `DMD`

**Read-only sur les events WS.**

Ces écrans n'appellent **aucun endpoint HTTP**. Ils ouvrent un WS sur `/ws?session_id=...` (ou `?room_code=...` pour observer une room entière) et consomment les events temps réel pour afficher du contenu visuel.

Mapping suggéré avec le `RuntimeEventMap` du front :

| Event WS reçu | RuntimeEventMap front |
|---|---|
| `score:update` | `score:update` (direct) |
| `ball:lost` | `ball:change` |
| `game:over` | `mode:change` (vers `gameOver`) |

---

## 4. Catalogue REST complet

### `GET /` — Healthcheck root

Réponse `200` :
```ts
{ message: "Flipper backend running" }
```

### `GET /health` (et `HEAD /health`)

Réponse `200` :
```ts
{ status: "ok" }
```

Pas d'erreur — c'est un sanity check.

---

### `/sessions` — gestion des sessions de jeu (Redis, éphémère)

#### `POST /sessions`

Crée une session de jeu en Redis (TTL sliding 30 min). Pas d'écriture en DB à ce stade.

**Request body**
```ts
interface CreateSessionRequest {
  pseudo: string;        // pattern: ^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$
  mode: GameMode;        // "solo" | "1v1" (défaut "solo")
  room_code: string | null;  // optionnel, pour mode 1v1
}
```

**Response 201**
```ts
interface CreateSessionResponse {
  session_id: string;    // UUID hex (32 chars), identifiant côté serveur
  pseudo: string;        // normalisé : uppercase + "#HETIC" si pas de hashtag fourni
  status: string;        // "waiting" à la création
  mode: string;          // "solo" | "1v1"
  room_code: string | null;
}
```

**Erreurs**
- `422` validation : pseudo ne matche pas le regex
- `422 InvalidPseudoError` : pseudo invalide remonté côté domaine (cas edge)

**Notes**
- Le pseudo est normalisé : `"abc"` devient `"ABC#HETIC"`, `"Foo#bar12"` devient `"FOO#BAR12"`. Le front doit donc utiliser la valeur **renvoyée** dans la response, pas celle saisie par l'utilisateur.
- Le `session_id` est l'identifiant principal pour tout le reste du flow (WS + POST /scores).

#### `POST /sessions/{session_id}/ready`

Marque la session comme prête (statut Redis `ready`).

**Path param** : `session_id` (string, UUID hex)

**Body** : aucun

**Response 200**
```ts
interface ReadyUpResponse {
  session_id: string;
  status: string;        // "ready"
}
```

**Erreurs**
- `404 SessionNotFoundError` : session inconnue ou expirée

---

### `/scores` — flush final (DB)

#### `POST /scores`

**Seul endpoint qui écrit en DB.** Lit la session Redis (score, mode, pseudo) + le buffer d'events MQTT accumulés, persiste tout en une transaction atomique, puis nettoie Redis.

**Request body**
```ts
interface FinishSessionRequest {
  sessionId: string;    // camelCase ! (alias serveur, en interne snake_case)
}
```

**Response 200** (camelCase pour le contrat client)
```ts
interface FinishSessionResponse {
  ok: boolean;          // true sur succès
  finalScore: number;
  playerId: number;     // id du Player persisté en DB
  gameId: number;       // id de la Game persistée
  eventCount: number;   // nb d'events flushés depuis le buffer Redis
  // Solo: bool. 1v1: null (pas de notion de record perso en duel)
  improved: boolean | null;
  previousBest: number | null;  // best solo précédent, null si première partie ou 1v1
}
```

**Erreurs**
- `404 SessionNotFoundError` : session expirée (TTL 30 min dépassé) ou déjà flushée
- `422` body manquant ou shape incorrect

**Règle "best score wins" (solo uniquement)**
- `improved=true` si nouveau score > best précédent (ou première partie solo de ce joueur)
- `improved=false` si nouveau score ≤ best précédent (la Game est quand même persistée)
- `improved=null` en mode 1v1 (chaque match est unique, pas de "record personnel" applicable)

---

### `/players` — gestion du profil joueur (DB)

#### `POST /players`

Idempotent : crée le Player si pas en DB, sinon renvoie celui existant.

**Request body**
```ts
interface CreatePlayerRequest {
  pseudo: string;       // pattern: ^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$
}
```

**Response 200**
```ts
interface PlayerResponse {
  id: number;
  pseudo: string;       // normalisé (uppercase + #HETIC si absent)
  created_at: string;   // ISO 8601
}
```

**Erreurs**
- `422` validation : pseudo invalide
- `422 InvalidPseudoError` : pseudo rejeté côté domaine

#### `GET /players/{player_id}`

Récupère un joueur par son id DB.

**Path param** : `player_id` (number)

**Response 200** : `PlayerResponse` (cf. ci-dessus)

**Erreurs**
- `404 PlayerNotFoundError` : id inconnu

#### `GET /players?pseudo={pseudo}`

Récupère un joueur par pseudo (normalisé côté serveur).

**Query** : `pseudo` (string, requis)

**Response 200** : `PlayerResponse`

**Erreurs**
- `404 PlayerNotFoundError` : pseudo non trouvé
- `422 InvalidPseudoError` : pseudo invalide

#### `GET /players/{player_id}/games?mode={mode}&limit={n}`

Historique des parties terminées d'un joueur, du plus récent au plus ancien.

**Path param** : `player_id` (number)

**Query**
- `mode` : `"solo" | "1v1"` (optionnel)
- `limit` : entier 1..100 (défaut `20`)

**Response 200**
```ts
interface PlayerHistoryResponse {
  player_id: number;
  pseudo: string;
  games: PlayerHistoryGameDTO[];  // triées par finished_at DESC
}

interface PlayerHistoryGameDTO {
  game_id: number;
  mode: string;         // "solo" | "1v1"
  score: number;
  started_at: string;   // ISO 8601
  finished_at: string;  // ISO 8601
  // true uniquement sur la game solo ayant le meilleur score du joueur.
  // Toujours false pour les games 1v1.
  is_best: boolean;
}
```

**Erreurs**
- `404 PlayerNotFoundError` : id inconnu
- `422` : `limit` hors `[1, 100]` ou `mode` non `"solo"` / `"1v1"`

---

### `/leaderboard` — classement

#### `GET /leaderboard?mode={mode}&limit={n}`

Top N scores. Une seule entrée par joueur (`MAX(score) GROUP BY player_id`).

**Query**
- `mode` : `"solo" | "1v1"` (optionnel — sans mode, agrège tous modes confondus)
- `limit` : entier 1..100 (défaut `10`)

**Response 200**
```ts
interface LeaderboardResponse {
  mode: string | null;       // echo du query param (null si non fourni)
  limit: number;
  entries: LeaderboardEntryDTO[];
}

interface LeaderboardEntryDTO {
  rank: number;              // 1-based
  player_id: number;
  pseudo: string;
  score: number;             // meilleur score du joueur (filtré par mode si fourni)
}
```

**Erreurs**
- `422` : `limit` hors `[1, 100]` ou `mode` non `"solo"` / `"1v1"`

**Notes**
- Seules les Games avec `status="finished"` sont prises en compte (sessions Redis ignorées).
- Plusieurs joueurs ayant choisi `ABC#HETIC` (sans hashtag custom) **partagent le même Player** en DB → 1 entrée dans le leaderboard. C'est intentionnel post-#100.

---

### `/rooms` — gestion des rooms (DB) — flow legacy

> 🚧 Ces routes existent mais relèvent du **flow legacy** (pré-Redis). Le nouveau flow utilise `/sessions` + WebSocket par session_id. Les rooms restent disponibles pour le mode 1v1 quand le matchmaking (#59) sera implémenté.

#### `POST /rooms`

**Request**
```ts
interface CreateRoomRequest {
  mode: GameMode;       // "solo" | "1v1"
}
```

**Response 201**
```ts
interface CreateRoomResponse {
  room_code: string;    // 6 caractères hex
  mode: string;
  status: string;       // "waiting"
  created_at: string;   // ISO 8601
}
```

**Erreurs**
- `400` : payload invalide
- `500` : erreur générique

#### `POST /rooms/{code}/join`

**Path param** : `code` (string, 6 chars)

**Response 200**
```ts
interface JoinRoomResponse {
  room_code: string;
  mode: string;
  status: string;
  games: RoomGameDTO[];
}

interface RoomGameDTO {
  game_id: number;
  player_id: number;
  score: number;
  status: string;
}
```

**Erreurs**
- `404` : room inconnue

#### `GET /rooms/list?status={status}`

**Query** : `status` (optionnel, ex: `"waiting"`)

**Response 200**
```ts
interface ListRoomsResponse {
  rooms: RoomListItemDTO[];
}

interface RoomListItemDTO {
  room_code: string;
  mode: string;
  status: string;
  created_at: string;   // ISO 8601
}
```

---

### `/games` — flow legacy (à utiliser uniquement pour debug)

> 🚧 Ces endpoints sont conservés pour rétrocompatibilité. Le **nouveau flow** est : `POST /sessions` → MQTT events → `POST /scores`. Le front n'a normalement pas besoin de `/games`.

| Endpoint | Description | Réponse |
|---|---|---|
| `POST /games/start` | Démarrer une game (DB) | `StartGameResponse` |
| `POST /games/{game_id}/events` | Ajouter un event (DB) | `AddEventResponse` |
| `POST /games/{game_id}/finish` | Terminer une game | `FinishGameResponse` |
| `GET /games/{game_id}` | Récupérer l'état d'une game | `GameStateResponse` |
| `GET /games/rooms/{code}/state` | État d'une room avec games + events | `RoomStateResponse` |
| `GET /games/list?status=X` | Lister les games | `ListGamesResponse` |

Schémas dans la section 7 (catalogue TypeScript).

---

## 5. Catalogue WebSocket

### `WS /ws?session_id={sid}` — **nouveau flow (recommandé)**

Souscription aux events d'une session de jeu. Un client par session.

**Query params** (mutuellement exclusifs)
- `session_id` (recommandé) : reçoit les events MQTT routés par `HandleMqttEventUseCase` pour cette session
- `room_code` (legacy) : reçoit tous les broadcasts d'une room

**Codes de fermeture serveur**
- `1000 "session_id or room_code required"` : aucun query param fourni
- `1000 "provide session_id OR room_code, not both"` : les deux fournis
- `1000 "session not found"` : `session_id` inexistant ou expiré (Redis)
- `1000 "room not found"` : `room_code` inexistant en DB

**Events serveur → client**

Tous les events ont la même forme `{ type: string, ...payload }` :

```ts
type WsEvent =
  | WsScoreUpdate
  | WsBallLost
  | WsGameOver;

interface WsScoreUpdate {
  type: "score:update";
  score: number;       // score cumulé après l'event
  combo: number;       // combo courant (reset à 0 sur ball:lost)
  // Si l'event vient de flipper/bumper/hit :
  bumperId?: number;
  // Si l'event vient de flipper/bonus :
  bonusType?: string;
}

interface WsBallLost {
  type: "ball:lost";
  livesRemaining: number;  // 0..3, décrémenté à chaque ball:lost
}

interface WsGameOver {
  type: "game:over";
  finalScore: number;
}
```

**Mapping avec `RuntimeEventMap` côté front**

| WsEvent | RuntimeEventMap front |
|---|---|
| `score:update` | `score:update` (identique) |
| `ball:lost` | `ball:change` (avec `{ livesRemaining }`) |
| `game:over` | `mode:change` (transition vers `gameOver`) + payload pour scoreboard |

**Events client → serveur**

Aucun event entrant n'est traité par le backend pour l'instant. Le client peut envoyer du texte mais c'est ignoré (la boucle `receive_text` sert juste à détecter la déconnexion).

**Politique de reconnexion attendue côté client**

- Exponential backoff : 1s, 2s, 4s, 8s, max 30s
- Avant chaque reconnexion : vérifier que la session est toujours vivante via... 🚧 *pas d'endpoint dédié, on peut juste tenter `POST /sessions/{id}/ready` qui renvoie 404 si la session a expiré*

### `WS /ws?room_code={code}` — flow legacy

Souscription aux broadcasts d'une room (tous les joueurs d'une room reçoivent les events de tous les autres). Conservé pour rétrocompatibilité.

Aucun event standardisé n'est broadcasté sur ce canal aujourd'hui par le nouveau flow Redis/MQTT (qui broadcaste par `session_id`). Ce canal était utilisé par l'ancien flow `/games` et reste fonctionnel mais inactif.

---

## 6. Référence MQTT (read-only pour le front)

Le frontend **ne parle pas MQTT directement**. Cette section explique d'où viennent les events WS qu'il reçoit.

**Architecture** :
```
[Flipper hardware] → publish → [Mosquitto broker] → subscribe → [Backend] → broadcast → [WebSocket client]
```

Le backend est abonné au topic filter `flipper/#` côté broker.

### Topics consommés

| Topic MQTT | Payload attendu | Mapping → event WS |
|---|---|---|
| `flipper/bumper/hit` | `{ bumperId: number, points: number, sessionId: string }` | `score:update { score, combo (incrémenté), bumperId }` |
| `flipper/bonus` | `{ type: string, points: number, sessionId: string }` | `score:update { score, combo, bonusType }` |
| `flipper/ball/lost` | `{ sessionId: string }` | `ball:lost { livesRemaining (décrémenté) }` |
| `flipper/game/over` | `{ sessionId: string }` | `game:over { finalScore }` |

Tout autre topic publié sous `flipper/#` est silencieusement ignoré (loggé en `debug`).

### Effets côté Redis (transparent pour le front)

Pour info, chaque event MQTT traité :
1. Mute la session Redis (score, lives, combo, status)
2. Push l'event brut dans une Redis List (consommée plus tard par `POST /scores`)
3. Broadcast la projection WS vers le hub de la session

Le front voit uniquement l'étape 3.

### Cas d'erreur MQTT

- Payload non-JSON ou non-objet → dropped silencieusement côté gateway
- `sessionId` manquant ou pointant vers une session expirée → log warning + drop, aucun event WS émis

---

## 7. Schémas TypeScript prêts à coller

Bloc unique à coller dans `src/services/api/types.ts` côté front. Conventions :
- `interface` pour les objets, `type` pour les unions
- Pas de classes, pas de zod, pas de dépendance externe
- `string` pour les dates ISO 8601 (avec commentaire)
- `field: T | null` quand le serveur renvoie `null` explicitement

```ts
// ─────────────────────────────────────────────────────────────
// Enums
// ─────────────────────────────────────────────────────────────

export type GameMode = "solo" | "1v1";

export type GameStatus = "playing" | "finished";

export type SessionStatus = "waiting" | "ready" | "playing" | "over";

export type RoomStatus = "waiting" | "playing" | "finished";

export type GameEventType =
  | "game_started"
  | "bumper_hit"
  | "ball_lost"
  | "bonus"
  | "flipper_hit"
  | "game_over"
  | "game_finished";

// ─────────────────────────────────────────────────────────────
// Format d'erreur standard
// ─────────────────────────────────────────────────────────────

export interface ApiError {
  error: string;   // ex: "PlayerNotFoundError"
  detail: string;  // message lisible
}

export interface PydanticValidationError {
  detail: Array<{
    loc: (string | number)[];
    msg: string;
    type: string;
    input?: unknown;
    ctx?: Record<string, unknown>;
  }>;
}

// ─────────────────────────────────────────────────────────────
// Sessions
// ─────────────────────────────────────────────────────────────

export interface CreateSessionRequest {
  pseudo: string;            // pattern: ^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$
  mode: GameMode;            // défaut "solo"
  room_code: string | null;
}

export interface CreateSessionResponse {
  session_id: string;        // UUID hex
  pseudo: string;            // normalisé serveur
  status: SessionStatus;     // "waiting" à la création
  mode: GameMode;
  room_code: string | null;
}

export interface ReadyUpResponse {
  session_id: string;
  status: SessionStatus;     // "ready"
}

// ─────────────────────────────────────────────────────────────
// Scores (POST /scores) — camelCase côté client
// ─────────────────────────────────────────────────────────────

export interface FinishSessionRequest {
  sessionId: string;
}

export interface FinishSessionResponse {
  ok: boolean;
  finalScore: number;
  playerId: number;
  gameId: number;
  eventCount: number;
  // null en 1v1 (pas de "record perso" applicable)
  improved: boolean | null;
  previousBest: number | null;
}

// ─────────────────────────────────────────────────────────────
// Players
// ─────────────────────────────────────────────────────────────

export interface CreatePlayerRequest {
  pseudo: string;            // même regex que sessions
}

export interface PlayerResponse {
  id: number;
  pseudo: string;
  created_at: string;        // ISO 8601
}

export interface PlayerHistoryGameDTO {
  game_id: number;
  mode: GameMode;
  score: number;
  started_at: string;        // ISO 8601
  finished_at: string;       // ISO 8601
  is_best: boolean;          // true sur la meilleure game solo du joueur
}

export interface PlayerHistoryResponse {
  player_id: number;
  pseudo: string;
  games: PlayerHistoryGameDTO[];   // ORDER BY finished_at DESC
}

// ─────────────────────────────────────────────────────────────
// Leaderboard
// ─────────────────────────────────────────────────────────────

export interface LeaderboardEntryDTO {
  rank: number;              // 1-based
  player_id: number;
  pseudo: string;
  score: number;
}

export interface LeaderboardResponse {
  mode: GameMode | null;
  limit: number;
  entries: LeaderboardEntryDTO[];
}

// ─────────────────────────────────────────────────────────────
// Rooms (legacy)
// ─────────────────────────────────────────────────────────────

export interface CreateRoomRequest {
  mode: GameMode;
}

export interface CreateRoomResponse {
  room_code: string;
  mode: GameMode;
  status: RoomStatus;
  created_at: string;        // ISO 8601
}

export interface RoomGameDTO {
  game_id: number;
  player_id: number;
  score: number;
  status: GameStatus;
}

export interface JoinRoomResponse {
  room_code: string;
  mode: GameMode;
  status: RoomStatus;
  games: RoomGameDTO[];
}

export interface RoomListItemDTO {
  room_code: string;
  mode: GameMode;
  status: RoomStatus;
  created_at: string;        // ISO 8601
}

export interface ListRoomsResponse {
  rooms: RoomListItemDTO[];
}

// ─────────────────────────────────────────────────────────────
// Games (legacy)
// ─────────────────────────────────────────────────────────────

export interface StartGameRequest {
  pseudo: string;
  mode: GameMode;
  room_code: string | null;
}

export interface StartGameResponse {
  player_id: number;
  room_code: string;
  game_id: number;
  event_id: number;
}

export interface AddEventRequest {
  type: GameEventType;
  points: number;            // défaut 0
}

export interface AddEventResponse {
  game_id: number;
  new_score: number;
  event_id: number;
}

export interface FinishGameResponse {
  game_id: number;
  status: GameStatus;        // "finished"
  finished_at: string;       // ISO 8601
  event_id: number;
}

export interface GameEventDTO {
  id: number;
  type: GameEventType;
  points: number;
  occured_at: string;        // ISO 8601
}

export interface GameStateResponse {
  game_id: number;
  player_id: number;
  score: number;
  status: GameStatus;
  started_at: string;        // ISO 8601
  finished_at: string | null;
  events: GameEventDTO[];
}

export interface RoomStateGameDTO {
  game_id: number;
  player_id: number;
  score: number;
  status: GameStatus;
  started_at: string;        // ISO 8601
  finished_at: string | null;
  events: GameEventDTO[];
}

export interface RoomStateResponse {
  room_code: string;
  mode: GameMode;
  status: RoomStatus;
  games: RoomStateGameDTO[];
}

export interface GameListItemDTO {
  game_id: number;
  room_id: number | null;
  player_id: number;
  score: number;
  status: GameStatus;
  mode: GameMode;
  started_at: string;        // ISO 8601
}

export interface ListGamesResponse {
  games: GameListItemDTO[];
}

// ─────────────────────────────────────────────────────────────
// WebSocket events (serveur → client) — nouveau flow par session
// ─────────────────────────────────────────────────────────────

export interface WsScoreUpdate {
  type: "score:update";
  score: number;
  combo: number;
  bumperId?: number;
  bonusType?: string;
}

export interface WsBallLost {
  type: "ball:lost";
  livesRemaining: number;
}

export interface WsGameOver {
  type: "game:over";
  finalScore: number;
}

export type WsEvent = WsScoreUpdate | WsBallLost | WsGameOver;
```

---

## 8. Format d'erreur standard

### Erreurs domaine (`ApiError`)

Toutes les erreurs levées explicitement par le backend (ressource non trouvée, conflit, pseudo invalide, etc.) suivent ce shape :

```json
{
  "error": "PlayerNotFoundError",
  "detail": "Player with id 999 not found"
}
```

**Mapping classe → code HTTP** :

| Classe `error` | Code HTTP | Quand |
|---|---|---|
| `PlayerNotFoundError` | 404 | `GET /players/{id}` ou `?pseudo=` introuvable |
| `RoomNotFoundError` | 404 | room_code inconnu |
| `GameNotFoundError` | 404 | game_id inconnu |
| `SessionNotFoundError` | 404 | session expirée ou inexistante (Redis) |
| `PlayerAlreadyExistsError` | 409 | pseudo déjà en base (rare, géré par upsert) |
| `GameAlreadyFinishedError` | 409 | tentative d'action sur une game déjà `finished` |
| `GameNotPlayableError` | 409 | tentative d'event sur une game qui n'est pas `playing` |
| `InvalidPseudoError` | 422 | pseudo ne respecte pas le format `XXX#YYYYY` |
| `DomainError` (générique) | 400 | autre erreur de domaine non spécialisée |

### Erreurs de validation Pydantic (`PydanticValidationError`)

Format différent (array `detail`) — déclenché par FastAPI **avant** le code applicatif quand le body / query ne matche pas le DTO Pydantic.

```json
{
  "detail": [
    {
      "loc": ["body", "pseudo"],
      "msg": "String should match pattern '^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$'",
      "type": "string_pattern_mismatch",
      "input": "AB"
    }
  ]
}
```

**Astuce front** : tester `typeof body.detail === "string"` → `ApiError`, sinon → `PydanticValidationError`.

---

## 9. État d'implémentation

✅ = implémenté et testé · 🟡 = implémenté, non testé · 🚧 = en cours · ❌ = pas commencé

| Endpoint / Event | Statut | Notes |
|---|---|---|
| `GET /` | ✅ | Healthcheck |
| `GET /health` | ✅ | |
| `POST /sessions` | ✅ | Couvert par 5 tests HTTP + 4 use case |
| `POST /sessions/{id}/ready` | ✅ | |
| `POST /scores` | ✅ | Best score wins (solo), camelCase response |
| `POST /players` | ✅ | Idempotent |
| `GET /players/{id}` | ✅ | |
| `GET /players?pseudo=X` | ✅ | |
| `GET /players/{id}/games` | ✅ | Inclut `is_best` |
| `GET /leaderboard` | ✅ | Filtre par mode + limit |
| `POST /rooms` | ✅ | Legacy, peu de tests |
| `POST /rooms/{code}/join` | ✅ | Legacy |
| `GET /rooms/list` | ✅ | Legacy |
| `POST /games/start` | ✅ | Legacy — préférer `POST /sessions` |
| `POST /games/{id}/events` | ✅ | Legacy |
| `POST /games/{id}/finish` | ✅ | Legacy |
| `GET /games/{id}` | ✅ | Legacy |
| `GET /games/rooms/{code}/state` | ✅ | Legacy |
| `GET /games/list` | ✅ | Legacy |
| `WS /ws?session_id=` | ✅ | Events `score:update`, `ball:lost`, `game:over` |
| `WS /ws?room_code=` | 🟡 | Endpoint fonctionnel, mais le nouveau flow ne broadcaste pas sur ce canal |
| Matchmaking 1v1 auto | ❌ | Issue #59 — pas de file d'attente, pas de `game:start` synchronisé |
| Pause/Resume endpoint | ❌ | Pas dans le scope actuel — pause UI-only |
| Header `X-Request-ID` | ✅ | Ajouté par le middleware logging à chaque réponse |
| Structured JSON logging | ✅ | Tous les logs serveur sont en JSON |

### Limitations connues

- **Pas d'auth** : tout client connaissant un `session_id` peut envoyer du WS / appeler `POST /scores` dessus. À sécuriser quand le projet dépassera le cadre interne.
- **TTL Redis 30 min sliding** : si l'utilisateur fait pause > 30 min sans interaction, la session expire et le score est perdu.
- **Doublons `#HETIC`** : deux joueurs qui tapent juste `ABC` partagent le même Player en DB. Voir l'issue #100 (mergée) pour le contexte et le mécanisme `improved/is_best` de mitigation.
- **Pas de pagination** dans `/leaderboard` et `/players/{id}/games` : `limit` borne à 100. Si besoin de plus, ouvrir une issue.

---

## Annexe — Tester rapidement en local

```bash
# 1. Démarrer la stack
docker compose up -d db redis mqtt

# 2. Lancer le serveur (depuis Flipper_back/)
DB_HOST=127.0.0.1 DB_PORT=5433 DB_USER=flipper_user DB_PASSWORD=flipper_password \
  DB_NAME=flipper REDIS_URL=redis://127.0.0.1:6379 \
  MQTT_BROKER_HOST=127.0.0.1 MQTT_BROKER_PORT=1883 \
  python3 -m app.main

# 3. Créer une session
curl -X POST localhost:8080/sessions \
  -H 'Content-Type: application/json' \
  -d '{"pseudo":"ABC","mode":"solo"}'

# 4. Ouvrir un WS (besoin de wscat: npm i -g wscat)
wscat -c "ws://localhost:8080/ws?session_id=<SESSION_ID_RETURNED>"

# 5. Simuler un event MQTT depuis le hardware
docker exec flipper_mqtt mosquitto_pub -t flipper/bumper/hit \
  -m '{"bumperId":1,"points":100,"sessionId":"<SESSION_ID>"}'

# 6. Le client wscat reçoit:
# {"type":"score:update","score":100,"combo":1,"bumperId":1}

# 7. Flusher en DB
curl -X POST localhost:8080/scores \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION_ID>"}'
```

> Le port host DB est **5433** localement (pour éviter une collision avec un autre Postgres sur 5432). En CI c'est 5432 standard.

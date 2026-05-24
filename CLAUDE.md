# CLAUDE.md — Flipper Game · BACKEND

> Tu travailles sur le **repo backend** `fouuuadi/Flipper_back` (branche par défaut : `main`).
> C'est aussi un **submodule** de `fouuuadi/Flipper_Center` (monorepo parent).
> Ne touche jamais au frontend. Ne génère pas de logique de rendu ou d'UI ici.

---

## ⚠️ CONTEXTE DE MIGRATION EN COURS

Ce projet existe déjà avec une base solide (Clean Archi, 70+ tests, CI/CD, Docker).
On migre vers une **nouvelle archi** (Redis sessions, MQTT IoT, écriture DB en fin de partie uniquement).

**Règle absolue** : avant de coder quoi que ce soit, identifie ce qui existe déjà et ce qu'on peut réutiliser.

---

## Stack technique

### Ce qui reste (✅ garder)

| Outil | Rôle |
|---|---|
| Python 3.12 | Langage |
| FastAPI 0.121.0 + Uvicorn | API REST + WebSocket |
| Pydantic v2 + pydantic-settings | Validation + config |
| pytest + pytest-asyncio + httpx | Tests |
| ruff + import-linter | Lint + contracts Clean Archi |
| GitHub Actions (ci.yml + build.yml) | CI/CD → GHCR |
| Docker Compose | Dev local |

### Ce qui change (🔄 migration)

| Avant | Après | Raison |
|---|---|---|
| MySQL 8.4 (aiomysql, SQL brut) | **PostgreSQL** (asyncpg, SQL brut) | Plus adapté, meilleur écosystème async |
| Écriture DB à chaque event | **Redis** pendant la partie, DB en fin seulement | Perf temps réel |
| Pas d'IoT | **MQTT** (aiomqtt) broker pour events physiques | Bumpers, capteurs flipper |
| Rooms comme entité principale | **Sessions** éphémères (Redis) + rooms persistées | Séparation éphémère/permanent |

### Ce qui s'ajoute (🆕 nouveau)

| Outil | Rôle |
|---|---|
| Redis (redis-py async client, Hash storage, sliding TTL 30 min) | Sessions de jeu en mémoire (score live, statut, pseudo) |
| MQTT broker (Mosquitto) | Réception events IoT (bumpers, ball lost, etc.) |
| aiomqtt | Client MQTT async pour FastAPI |

---

## Architecture — Clean Architecture (4 couches, déjà en place)

```
app/
├── config.py                          # ✅ Settings pydantic-settings (ADAPTER pour PG + Redis + MQTT)
├── di.py                              # ✅ Composition root (ADAPTER pour nouveaux repos + services)
├── main.py                            # ✅ Entry FastAPI + lifespan (ADAPTER pour Redis + MQTT connect)
├── domain/                            # ✅ GARDER — couche métier pure
│   ├── player.py, room.py, game.py    # ✅ Entités Pydantic existantes
│   ├── game_event.py, match.py        # ✅ Garder
│   ├── session.py                     # 🆕 Entité Session (éphémère, pas en DB)
│   ├── leaderboard_entry.py           # 🆕 Entité projection (rank, player_id, pseudo, score)
│   ├── pseudo.py                      # 🆕 Helper format pseudo XXX#YYYYY + DEFAULT_HASHTAG=HETIC
│   ├── exceptions.py                  # ✅ DomainError + InvalidPseudoError + filles
│   └── ports/                         # ✅ Interfaces ABC existantes
│       ├── player_repository.py       # ✅ Garder
│       ├── game_repository.py         # ✅ Garder
│       ├── game_event_repository.py   # ✅ Garder
│       ├── room_repository.py         # ✅ Garder
│       ├── session_store.py           # ✅ Port ABC pour sessions Redis
│       ├── mqtt_gateway.py            # ✅ Port ABC pour le bridge MQTT
│       ├── session_event_broadcaster.py  # ✅ Port ABC pour broadcaster par session_id
│       └── event_buffer.py            # 🆕 Port ABC pour buffer d'events MQTT en Redis
├── infrastructure/
│   ├── db/
│   │   ├── postgres.py                # 🔄 Remplace mysql.py (pool asyncpg)
│   │   ├── player_repository.py       # 🔄 Renommer PgPlayerRepository (adapter SQL)
│   │   ├── game_repository.py         # 🔄 PgGameRepository
│   │   ├── game_event_repository.py   # 🔄 PgGameEventRepository
│   │   ├── room_repository.py         # 🔄 PgRoomRepository
│   │   └── mappers/                   # ✅ Garder (adapter si colonnes changent)
│   ├── redis/
│   │   ├── client.py                  # 🆕 Connexion Redis async
│   │   └── session_store.py           # 🆕 RedisSessionStore(SessionStore)
│   ├── mqtt/
│   │   └── mqtt_service.py            # 🆕 Subscribe broker + dispatch vers usecases
│   └── ws/
│       └── room_hub.py                # ✅ Garder (broadcast WS par room)
├── usecase/                           # ✅ Garder la structure, adapter/ajouter
│   ├── create_room_usecase.py         # ✅
│   ├── join_room_usecase.py           # ✅
│   ├── start_game_usecase.py          # 🔄 Adapter : créer session Redis au lieu d'écrire en DB
│   ├── add_game_event_usecase.py      # 🔄 Adapter : accumuler dans Redis, pas en DB
│   ├── finish_game_usecase.py         # 🔄 Adapter : flush Redis → DB (seul moment d'écriture)
│   ├── create_session_usecase.py      # 🆕 Créer session éphémère (pseudo → Redis)
│   ├── ready_up_usecase.py            # 🆕 Marquer joueur "prêt" + trigger game:start si tous prêts
│   ├── handle_mqtt_event_usecase.py   # 🆕 Recevoir event MQTT → mettre à jour session → broadcaster WS
│   ├── finish_and_persist_usecase.py  # 🆕 Flush session Redis → DB atomique (POST /scores)
│   ├── create_or_get_player_usecase.py # 🆕 Upsert idempotent Player par pseudo
│   ├── get_player_usecase.py          # 🆕 Lookup Player par id ou pseudo
│   └── get_leaderboard_usecase.py     # 🆕 Top N scores filtrables par mode
└── transport/
    ├── http/
    │   ├── root.py, health.py         # ✅
    │   ├── rooms.py                   # ✅
    │   ├── games.py                   # ✅
    │   ├── sessions.py                # 🆕 POST /sessions, POST /sessions/{id}/ready
    │   ├── scores.py                  # 🆕 POST /scores (flush final → DB)
    │   ├── players.py                 # 🆕 POST /players, GET /players/{id}, GET /players?pseudo=X
    │   ├── leaderboard.py             # 🆕 GET /leaderboard?mode=&limit=
    │   ├── error_handler.py           # ✅
    │   ├── dtos.py                    # ✅ (étendre)
    │   └── schemas/                   # ✅ (étendre)
    └── ws/
        └── handler.py                 # 🔄 Adapter : WS par session_id en plus de room_code
tests/                                 # ✅ 70+ tests existants — NE RIEN CASSER, ajouter
db/init/                               # 🔄 Adapter pour PostgreSQL
```

---

## Flow serveur — nouvelle archi

### Phase 1 — Avant la partie (HTTP pur)

```
POST /sessions
  ← { pseudo: "ABC" }
  → Générer pseudo formaté ABC#4521
  → Créer session Redis : { sessionId, pseudo, score: 0, status: "waiting" }
  → Répondre { sessionId, pseudo }
  ⚠️ PAS d'écriture en DB ici

POST /sessions/{sessionId}/ready
  ← (rien)
  → Redis : status → "ready"
  → Si mode 1v1 : vérifier si tous prêts dans la room
  → Si tous prêts : broadcaster WS event "game:start"
  → Ouvrir le handshake WebSocket côté client à ce moment
```

### Phase 2 — Pendant la partie (WebSocket + MQTT)

```
WS /ws?session_id=XXX
  → Handshake WebSocket
  → Connexion maintenue pendant toute la partie

MQTT broker → FastAPI subscriber
  Topic: flipper/bumper/hit     → { bumperId, points, sessionId }
  Topic: flipper/ball/lost      → { sessionId }
  Topic: flipper/game/over      → { sessionId }

Bridge MQTT → UseCase → Redis (score update) → WS broadcast
  ← "score:update"  { score, combo, bumperId }
  ← "ball:lost"     { livesRemaining }
  ← "game:over"     { finalScore }
```

### Phase 3 — Fin de partie (HTTP, seul moment d'écriture DB)

```
POST /scores
  ← { sessionId }
  → Lire session depuis Redis (score final, pseudo, events accumulés)
  → INSERT Player si pas existant (ON CONFLICT pseudo)
  → INSERT Game (score, timestamps)
  → INSERT GameEvents (batch, tous les events accumulés)
  → Supprimer session Redis
  → Répondre { ok, finalScore, playerId }
```

---

## MQTT — événements IoT attendus

| Topic MQTT | Payload | Action backend |
|---|---|---|
| `flipper/bumper/hit` | `{ bumperId, points, sessionId }` | Score += points dans Redis, WS broadcast |
| `flipper/flipper/hit` | `{ side, sessionId }` | Event enregistré dans Redis |
| `flipper/ball/lost` | `{ sessionId }` | Décrémenter vies, possiblement game over |
| `flipper/bonus` | `{ type, points, sessionId }` | Score += points, WS broadcast |
| `flipper/game/over` | `{ sessionId }` | Broadcaster "game:over", déclencher flush DB |

> Le broker MQTT (Mosquitto) tourne dans un container Docker séparé.

---

## Contracts Clean Archi (import-linter, NE PAS CASSER)

Les 4 contracts existants dans `.importlinter` DOIVENT continuer à passer :

1. `domain` n'importe RIEN d'autre
2. `usecase` n'importe PAS `transport`
3. `transport` n'importe PAS `infrastructure.db` (sauf via `app.di`)
4. Layering strict : `domain < infrastructure < usecase < transport`

**Conséquences pour les nouveaux modules :**
- `infrastructure/redis/` et `infrastructure/mqtt/` suivent les mêmes règles que `infrastructure/db/`
- Les ports (`session_store.py`, `mqtt_gateway.py`) vont dans `domain/ports/`
- Le wiring se fait dans `app/di.py` uniquement

---

## Règles strictes du projet

### ❌ NE JAMAIS

- Committer `.env` ou des secrets en clair
- Utiliser du code synchrone/bloquant (tout `async/await`)
- Mettre de logique métier dans `transport/`
- Accéder à la DB/Redis directement depuis `domain/`
- Pusher directement sur `main` — toujours une PR
- Ignorer un échec Trivy (`HIGH`) en CI
- Ajouter des dépendances sans version épinglée dans `requirements.txt`
- Écrire en DB pendant une partie (Redis only pendant le jeu)

### ✅ TOUJOURS

- **Conventional Commits** en anglais : `feat(scope):`, `fix(scope):`, `refactor(scope):`, `chore(scope):`
- Tests pour tout nouveau code : `pytest tests/ -v`
- Lint clean : `ruff check .` + `lint-imports` (4 contracts)
- 1 branche = 1 PR = 1 intention
- Claude ne commit/push/merge pas — c'est le dev qui fait
- Commentaires uniquement là où la logique est non-évidente

---

## Variables d'environnement (cible)

```env
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=flipper
DB_USER=flipper
DB_PASSWORD=

# Redis
REDIS_URL=redis://localhost:6379

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# App
APP_PORT=8000
```

---

## Plan de migration — ordre recommandé

> Chaque étape = 1 branche = 1 PR. Ne pas tout faire d'un coup.

### Étape 1 — Infrastructure Redis ✅ (PR #91)
- [x] Ajouter Redis au `docker-compose.yml`
- [x] `infrastructure/redis/client.py` — connexion async
- [x] `domain/ports/session_store.py` — port ABC
- [x] `infrastructure/redis/session_store.py` — implémentation (Hash + sliding TTL)
- [x] Wiring dans `di.py`
- [x] Tests unitaires (mock) + intégration (Redis réel)

### Étape 2 — Sessions endpoints ✅ (PR #92)
- [x] `usecase/create_session_usecase.py` (UUID + pseudo formaté ABC#4521)
- [x] `usecase/ready_up_usecase.py`
- [x] `transport/http/sessions.py` — POST /sessions, POST /sessions/{id}/ready
- [x] Tests

### Étape 3 — MQTT bridge ✅ (PR #93)
- [x] Mosquitto dans `docker-compose.yml` + CI
- [x] `domain/ports/mqtt_gateway.py` — port ABC (MqttEvent + handler Protocol)
- [x] `infrastructure/mqtt/aio_mqtt_gateway.py` — subscribe `flipper/#` + dispatch JSON
- [x] Connecter au lifespan FastAPI
- [x] Tests d'intégration broker réel

### Étape 4 — Bridge MQTT → Redis → WebSocket ✅ (PR #94)
- [x] `usecase/handle_mqtt_event_usecase.py` — route topic → mute session → broadcast
- [x] `domain/ports/session_event_broadcaster.py` + `infrastructure/ws/session_hub.py`
- [x] `/ws` accepte `?session_id=` OU `?room_code=` (XOR)
- [x] Session étendue avec `lives` + `combo`
- [x] Tests unit (use case, hub)

### Étape 5 — Flush final (POST /scores) 🚧 (PR #88 — branche `feat/post-scores-flush`)
- [ ] `domain/ports/event_buffer.py` + `infrastructure/redis/event_buffer.py` (Redis List, accumule events MQTT pendant la partie)
- [ ] `mode` ajouté à Session
- [ ] `GameRepository.persist_finished_session(...)` — transaction atomique (Player upsert + Game + GameEvents batch)
- [ ] `usecase/finish_and_persist_usecase.py`
- [ ] `transport/http/scores.py` — POST /scores
- [ ] Tests

### Étape 6 — Migration MySQL → PostgreSQL
- [ ] Adapter `docker-compose.yml` (PostgreSQL au lieu de MySQL)
- [ ] `infrastructure/db/postgres.py` remplace `mysql.py`
- [ ] Adapter tous les `MysqlXxxRepository` → `PgXxxRepository`
- [ ] Adapter les scripts `db/init/`
- [ ] Adapter les 70+ tests existants
- [ ] Mettre à jour CI

### Étape 7 — Issues existantes (après migration)
- [ ] #68 Unit of Work (transactions atomiques)
- [ ] #69 EventBus interne
- [ ] #70 WebSocket broadcast par room
- [ ] #71 Structured logging JSON

---

## Ce qui est déjà fait (état actuel)

- [x] Setup FastAPI + Clean Archi 4 couches
- [x] MySQL avec aiomysql (SQL brut, pas d'ORM)
- [x] Entités Pydantic (Player, Room, Game, GameEvent, Match)
- [x] Ports/Interfaces dans `domain/ports/`
- [x] Mappers (row → entity)
- [x] Custom domain exceptions + global error handler
- [x] DTO schemas request/response
- [x] pydantic-settings config
- [x] WebSocket broadcast par room (room_hub.py)
- [x] 70+ tests (pytest)
- [x] CI/CD GitHub Actions → GHCR
- [x] Docker Compose (MySQL + phpMyAdmin + backend)
- [x] ruff + import-linter (4 contracts)
- [x] Redis sessions (port + Redis Hash impl + sliding TTL)
- [x] Sessions HTTP endpoints (POST /sessions, POST /sessions/{id}/ready)
- [x] MQTT broker bridge (Mosquitto + aiomqtt + port + impl)
- [x] Bridge MQTT → Redis → WebSocket (session-scoped broadcast)
- [x] SessionEventBroadcaster port + SessionHubManager
- [ ] POST /scores (flush final) — en cours sur `feat/post-scores-flush`
- [ ] EventBuffer port + Redis List impl — en cours sur `feat/post-scores-flush`
- [ ] Migration PostgreSQL

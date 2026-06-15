# Architecture — Flipper Backend

> Doc vivante. Décrit la **structure statique** du code : les couches, les règles de
> dépendance, le pattern ports/adapters et la composition root.
>
> Pour le **flux runtime** d'une partie (séquence des appels, MQTT → Redis → WS → DB),
> voir [`WORKFLOW.md`](./WORKFLOW.md). Pour le contrat côté client, voir
> [`FRONTEND_INTEGRATION.md`](./FRONTEND_INTEGRATION.md) et [`MATCH_SYNC.md`](./MATCH_SYNC.md).

---

## 1. Principe directeur — Clean Architecture

Le backend suit une **Clean Architecture à 4 couches**. La règle fondamentale (la
*Dependency Rule*) : **les dépendances ne pointent que vers l'intérieur**.

```
        ┌─────────────────────────────────────────────────────┐
        │  transport/   (HTTP routes, WebSocket handlers)      │  ← le plus externe
        │     │                                                │
        │     ▼                                                │
        │  usecase/     (orchestration métier, 1 cas = 1 file) │
        │     │                                                │
        │     ▼                                                │
        │  infrastructure/  (asyncpg, redis, aiomqtt, ws hubs) │
        │     │                                                │
        │     ▼                                                │
        │  domain/      (entités + ports, zéro dépendance)     │  ← le plus interne
        └─────────────────────────────────────────────────────┘

        Sens autorisé des imports :  externe ──────► interne
        Jamais l'inverse.
```

Concrètement :

- `domain` ne connaît **personne**. Pas de FastAPI, pas d'asyncpg, pas de Redis.
- `infrastructure` connaît `domain` (il implémente ses ports) mais ignore `usecase`/`transport`.
- `usecase` connaît `domain` et reçoit ses dépendances par **injection** (jamais d'import direct d'un adapter concret, sauf via les types de ports).
- `transport` est le point d'entrée, il câble tout via `app/di.py`.

L'intérêt : le cœur métier (`domain` + `usecase`) est **testable sans I/O** (on injecte des fakes), et on peut changer une techno d'infra (MySQL → PostgreSQL, ce qui a déjà été fait) sans toucher au métier.

---

## 2. Les 4 couches en détail

### `domain/` — le cœur métier pur

Aucune dépendance externe (ni framework, ni driver). Contient deux choses :

| Élément | Fichiers | Rôle |
|---|---|---|
| **Entités** | `player.py`, `room.py`, `game.py`, `game_event.py`, `match.py`, `session.py`, `leaderboard_entry.py` | Objets métier Pydantic v2 |
| **Helpers métier** | `pseudo.py` (format `XXX#YYYYY`, `DEFAULT_HASHTAG="HETIC"`), `exceptions.py` (`DomainError` + filles) | Logique pure |
| **Ports** (`domain/ports/`) | `*_repository.py`, `session_store.py`, `event_buffer.py`, `mqtt_gateway.py`, `session_event_broadcaster.py`, `unit_of_work.py` | Interfaces ABC — *contrats* que l'infra doit remplir |

> Les **ports** sont la clé de l'inversion de dépendance (cf. §3). Ils vivent dans
> `domain` parce que c'est le métier qui *décrit ce dont il a besoin*, pas l'infra qui
> impose ce qu'elle offre.

### `infrastructure/` — les adapters (I/O concret)

Implémente les ports du domaine avec des technos réelles. Une sous-couche par techno :

| Sous-dossier | Contenu | Implémente |
|---|---|---|
| `db/` | `postgres.py` (pool asyncpg), `Pg*Repository`, `unit_of_work.py`, `mappers/` (row → entity) | `*Repository`, `UnitOfWork` |
| `redis/` | `client.py`, `session_store.py`, `event_buffer.py` | `SessionStore`, `EventBuffer` |
| `mqtt/` | `aio_mqtt_gateway.py` (client aiomqtt + consumer task) | `MqttGateway` |
| `ws/` | `room_hub.py` (legacy room-scoped), `session_hub.py` (session-scoped) | `SessionEventBroadcaster` |

Détail important : les `Pg*Repository` acceptent **soit un `Pool`** (usage standalone),
**soit une `Connection`** (quand ils tournent sous une `UnitOfWork`, pour partager une
transaction). Voir `_executor.py` et `unit_of_work.py`.

### `usecase/` — l'orchestration métier

Un fichier = un cas d'usage = une classe avec une méthode `execute(...)`. Le use case
reçoit ses dépendances **typées par les ports** (jamais par les classes concrètes), via
son `__init__`. Il ne sait pas si derrière c'est PostgreSQL ou un fake de test.

Familles de use cases (détail des responsabilités dans `WORKFLOW.md`) :

- **Flow d'une partie** : `create_session`, `ready_up`, `handle_mqtt_event`, `finish_and_persist`
- **Match sync** : `pause_session`, `resume_session`, `abandon_session`, `start_countdown`
- **Flow legacy rooms/games** : `create_room`, `join_room`, `start_game` (utilise l'`UnitOfWork`), `add_game_event`, `finish_game`, `get_room_state`, `get_game_state`, `list_rooms_games`
- **Hors flow (profil/stats)** : `create_or_get_player`, `get_player`, `get_leaderboard`, `get_player_history`

### `transport/` — les points d'entrée

Traduit le monde extérieur (HTTP/WS) en appels de use cases. **Zéro logique métier ici**
(règle stricte du projet) : on parse/valide l'entrée, on instancie le use case via `di`,
on mappe la sortie vers un DTO de réponse.

| Sous-dossier | Contenu |
|---|---|
| `http/` | Routers FastAPI (`sessions.py`, `scores.py`, `players.py`, `leaderboard.py`, `rooms.py`, `games.py`, `health.py`, `root.py`), `schemas/` (requêtes/réponses Pydantic), `dtos.py`, `error_handler.py` (mappe `DomainError` → HTTP), `logging_middleware.py` |
| `ws/` | `handler.py` (`/ws?session_id=` XOR `?room_code=`), `hub.py` |

---

## 3. Pattern Ports & Adapters (inversion de dépendance)

C'est le mécanisme qui permet à `usecase` de rester pur tout en faisant de l'I/O.

```
   domain/ports/session_store.py        usecase/create_session_usecase.py
   ┌──────────────────────────┐         ┌─────────────────────────────────┐
   │  class SessionStore(ABC) │◄────────│ def __init__(self, store:        │
   │    async def create(...) │  dépend │              SessionStore): ...  │
   │    async def get(...)    │  de     │ # appelle store.create(...)      │
   └──────────────────────────┘ l'abstr.└─────────────────────────────────┘
              ▲
              │ implémente (la flèche de dépendance pointe vers le domaine)
   ┌──────────────────────────────────────┐
   │ infrastructure/redis/session_store.py │
   │   class RedisSessionStore(SessionStore)│
   └──────────────────────────────────────┘
```

- Le use case **dépend de l'abstraction** (`SessionStore`), pas de `RedisSessionStore`.
- L'adapter concret **dépend du domaine** (il importe et hérite du port).
- Résultat : la flèche de dépendance va toujours vers `domain`, même si à l'exécution
  c'est `infrastructure` qui fait le vrai travail. C'est l'**inversion de dépendance**.

En test : on passe un `FakeSessionStore` qui implémente le même port → le use case ne
voit pas la différence, aucune I/O réelle.

---

## 4. Composition root — `app/di.py`

Le seul endroit où les classes concrètes rencontrent les ports. C'est là qu'on
**assemble** l'application.

```python
# Singletons d'infra, posés au démarrage (lifespan dans app/main.py)
set_db_pool(pool)          # asyncpg.Pool
set_redis_client(client)   # redis.asyncio.Redis
set_mqtt_gateway(gateway)  # AioMqttGateway

# Providers consommés par transport (retournent des types de PORTS)
get_player_repo()    -> PlayerRepository      # = PgPlayerRepository(pool)
get_session_store()  -> SessionStore          # = RedisSessionStore(client, ttl)
get_event_buffer()   -> EventBuffer           # = RedisEventBuffer(client, ttl)
get_uow()            -> UnitOfWork            # = PgUnitOfWork(pool), une instance fraîche par appel
get_mqtt_gateway()   -> MqttGateway
get_session_hub_manager() / get_hub_manager() # singletons WS
```

Points clés :

- **Cycle de vie** : `set_*` sont appelés une fois au démarrage (lifespan FastAPI dans
  `app/main.py`). Les `get_*_repo()` recréent un repo léger par appel autour du pool partagé.
- **`get_uow()` renvoie une instance neuve** à chaque appel : `__aenter__` acquiert sa
  propre connexion et ouvre sa propre transaction. Usage : `async with uow: ...`.
- Les providers retournent des **types de ports**, jamais les classes concrètes — c'est
  ce qui garde `transport` découplé de l'infra.

---

## 5. Les 4 contracts import-linter (NE PAS CASSER)

Vérifiés en CI via `lint-imports` (config dans `.importlinter`). Ils *mécanisent* les
règles ci-dessus :

| # | Contract | Règle |
|---|---|---|
| 1 | `layers` | Layering strict : `transport` > `usecase` > `infrastructure` > `domain`. Une couche ne peut importer que vers l'intérieur. |
| 2 | `domain-independence` | `domain` ne peut importer **ni** `infrastructure`, `usecase`, `transport`. |
| 3 | `usecase-no-transport` | `usecase` ne peut **pas** importer `transport`. |
| 4 | `transport-no-direct-db` | `transport` ne peut **pas** importer `infrastructure.db`… |

**La seule dérogation au contract 4** : `app.di` est autorisé à importer les repos et la
UoW de `infrastructure.db` (`ignore_imports` dans `.importlinter`). C'est voulu — `di` est
la composition root, son boulot est précisément de connaître les implémentations
concrètes. Le reste de `transport` passe par les providers `get_*()`.

> ⚠️ Si tu ajoutes un nouveau repo SQL câblé dans `di.py`, il faut ajouter la ligne
> correspondante dans `ignore_imports`, sinon le contract 4 casse en CI.

---

## 6. Où mettre quoi — guide de décision

| Tu ajoutes… | Ça va dans… |
|---|---|
| Une nouvelle entité métier ou une règle pure | `domain/` (entité) + éventuellement `domain/exceptions.py` |
| Un besoin d'I/O exprimé par le métier (nouveau type de stockage, gateway…) | un **port** ABC dans `domain/ports/` |
| L'implémentation concrète de ce port (driver, client) | `infrastructure/<techno>/` |
| Un nouveau cas d'usage / orchestration | `usecase/<nom>_usecase.py` (+ injecter les ports nécessaires) |
| Un nouvel endpoint HTTP ou message WS | `transport/http/` ou `transport/ws/` + un schéma dans `transport/http/schemas/` |
| Le câblage entre un port et son implémentation | `app/di.py` **uniquement** |

Règle mnémotechnique : **descends la stack** `domain → infrastructure → usecase → transport`
quand tu construis une feature (c'est l'ordre que suit l'agent `backend-builder`).

---

## 7. Vérifier la conformité

```bash
ruff check .          # lint
lint-imports          # les 4 contracts Clean Archi
pytest tests/ -v      # 70+ tests (unit + intégration)
```

Les trois doivent passer avant toute PR. La CI (`.github/workflows/ci.yml`) les rejoue,
avec les services `postgres:16-alpine`, `redis` et `mosquitto` pour les tests d'intégration.

# Tests — Flipper Backend

> Doc vivante. Décrit **la stratégie de test** du backend : ce qu'on teste, comment,
> avec quels outils, et comment lancer la suite en local comme en CI.
>
> Pour la structure statique du code (couches, ports/adapters), voir
> [`ARCHITECTURE.md`](./ARCHITECTURE.md). Pour le flux runtime d'une partie, voir
> [`WORKFLOW.md`](./WORKFLOW.md).

---

## 1. Stratégie — une pyramide qui suit la Clean Archi

Le découpage en couches (cf. `ARCHITECTURE.md`) rend le cœur métier testable **sans I/O** :
un use case reçoit ses dépendances par les ports, donc en test on lui passe des **fakes**
en mémoire. Résultat, deux niveaux bien distincts :

```
        ┌────────────────────────────────────────────┐
        │  Intégration  (vraie DB / Redis / MQTT)     │  ← repos, stores, routes HTTP
        │     postgres + redis + mosquitto réels      │
        ├────────────────────────────────────────────┤
        │  Unitaire  (fakes en mémoire, zéro I/O)     │  ← use cases, hubs, mappers, domain
        │     rapide, isolé, l'essentiel des tests    │
        └────────────────────────────────────────────┘
```

- **Unitaire** : la majorité. Les use cases sont testés avec des fakes qui implémentent
  les mêmes ports que la prod. Aucune base, aucun réseau → rapide et déterministe.
- **Intégration** : les adapters concrets (`Pg*Repository`, `Redis*Store`, routes HTTP de
  bout en bout) sont testés contre une **vraie** instance Postgres / Redis / MQTT, pour
  valider le SQL, les TTL Redis et le câblage FastAPI.

---

## 2. Stack & configuration

| Outil | Version | Rôle |
|---|---|---|
| `pytest` | 8.3.5 | Runner de test |
| `pytest-asyncio` | 0.26.0 | Support `async def test_…` |

Config dans **`pytest.ini`** :

```ini
[pytest]
asyncio_mode = auto                              # pas besoin de @pytest.mark.asyncio partout
asyncio_default_fixture_loop_scope = function    # une event loop fraîche par test
```

`asyncio_mode = auto` : toute fonction `async def test_*` est exécutée comme un test async
sans décorateur explicite. La boucle est recréée à chaque test (scope `function`) pour
éviter les fuites d'état entre tests.

---

## 3. Organisation des tests

Tout vit dans **`tests/`** : **48 fichiers**, **265 fonctions de test**. Convention de
nommage : `test_<sujet>.py`, et le sujet reprend le nom du module testé
(`test_start_game_usecase.py` ↔ `app/usecase/start_game_usecase.py`).

### Couverture par couche

| Couche | Exemples de fichiers de test | Type |
|---|---|---|
| **Use cases** | `test_start_game_usecase.py`, `test_handle_mqtt_event_usecase.py`, `test_apply_borne_intent_usecase.py`, `test_finish_and_persist_usecase.py` | Unitaire (fakes) |
| **Repositories DB** | `test_player_repository.py`, `test_unit_of_work.py`, `test_list_rooms_games.py` | Intégration (Postgres réel) |
| **Stores Redis** | `test_session_store.py`, `test_event_buffer.py`, `test_borne_store.py` | Intégration (Redis réel) |
| **Routes HTTP** | `test_players_http.py`, `test_leaderboard_http.py`, `test_sessions_http.py`, `test_scores_http.py` | Intégration (TestClient + infra) |
| **WebSocket / hubs** | `test_borne_hub.py`, `test_session_hub.py`, `test_ws_session_commands.py`, `test_borne_handler.py` | Unitaire (mocks WS) |
| **MQTT** | `test_mqtt_gateway.py` | Unitaire (aiomqtt mocké) |
| **Domain & config** | `test_mappers.py`, `test_pseudo.py`, `test_domain_exceptions.py`, `test_config.py`, `test_logging_config.py`, `test_health.py` | Unitaire |

---

## 4. Les doubles de test (fakes vs mocks)

Deux techniques cohabitent, choisies selon ce qu'on isole :

### a) Fakes en mémoire — pour les ports métier

Quand un use case dépend d'un port (`SessionStore`, `BorneStore`, `*Broadcaster`…), on
écrit une implémentation **fake** qui stocke en mémoire et enregistre les appels. Définie
directement dans le fichier de test, elle implémente le même contrat que la prod.

```python
# extrait de test_handle_mqtt_event_usecase.py
class _InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
    async def get(self, session_id):
        return self._sessions.get(session_id)
    async def update(self, session):
        self._sessions[session.session_id] = session

class _RecordingBroadcaster:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
    async def broadcast_to_session(self, session_id, message):
        self.calls.append((session_id, message))   # on asserte ensuite sur .calls
```

Avantage : on vérifie le **comportement** (« le bon message a-t-il été diffusé ? ») sans
réseau ni base.

### b) `unittest.mock.AsyncMock` — pour les WebSockets

Pour les hubs, le « client » est une WebSocket. On le remplace par un `AsyncMock` et on
asserte que `send_json` a été appelé avec le bon payload :

```python
# extrait de test_borne_hub.py
ws1, ws2 = AsyncMock(), AsyncMock()
await hub.add_client(ws1)
await hub.broadcast({"type": "nav:state", "nav": "menu"})
ws1.send_json.assert_awaited_once_with({"type": "nav:state", "nav": "menu"})
```

### c) Vraie infra — pour les adapters

Les tests d'intégration utilisent les fixtures de **`tests/conftest.py`** :

| Fixture | Rôle |
|---|---|
| `db_pool` | Ouvre un pool asyncpg vers le Postgres de test (env `DB_*`) |
| `clean_tables` | `TRUNCATE … RESTART IDENTITY CASCADE` avant chaque test → isolation |

Les stores Redis ont leur propre fixture `redis_client` (vraie connexion, flush entre tests).

---

## 5. Lancer les tests

### En local

Les tests d'intégration ont besoin de Postgres, Redis et un broker MQTT. Le plus simple
en conteneurs :

```bash
# 1. Infra de test
docker run -d --name flip_pg   -e POSTGRES_DB=flipper -e POSTGRES_USER=flipper \
  -e POSTGRES_PASSWORD=flipperpass -p 5432:5432 postgres:16-alpine
docker run -d --name flip_redis -p 6379:6379 redis:7-alpine
docker run -d --name flip_mqtt  -p 1883:1883 \
  -v "$PWD/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" eclipse-mosquitto:2

# 2. Schéma DB
for f in db/init/*.sql; do psql -h 127.0.0.1 -U flipper -d flipper -f "$f"; done

# 3. Variables d'env (mêmes clés qu'en CI, cf. §6) puis :
pytest tests/ -v
```

Exemples ciblés :

```bash
pytest tests/test_handle_mqtt_event_usecase.py -v        # un fichier
pytest tests/ -k "leaderboard"                           # par mot-clé
pytest tests/test_borne_hub.py::test_broadcast_sends_to_all_clients   # un seul test
```

> Les tests **unitaires** (use cases, mappers, hubs…) tournent sans infra. Seuls les tests
> d'intégration échouent si Postgres/Redis/MQTT ne sont pas là.

### En CI

`.github/workflows/ci.yml` (job `test`) rejoue toute la suite. Il démarre les services
`postgres:16-alpine` + `redis` + `mosquitto`, applique `db/init/*.sql`, puis lance
`pytest tests/ -v` avec ces variables d'environnement :

```
APP_PORT=8080
DB_HOST=127.0.0.1   DB_PORT=5432   DB_USER=flipper   DB_PASSWORD=flipperpass   DB_NAME=flipper
REDIS_URL=redis://127.0.0.1:6379   REDIS_SESSION_TTL_SECONDS=1800
MQTT_BROKER_HOST=127.0.0.1   MQTT_BROKER_PORT=1883
MQTT_TOPIC_FILTER=flipper/#   MQTT_BORNE_INPUT_TOPIC_FILTER=pinball/+/input/#
BORNE_ID=borne-ci   LOG_LEVEL=INFO
```

Le même job CI lance aussi `lint-imports` (les 4 contrats Clean Archi) et `ruff` : les
trois doivent passer avant un merge.

---

## 6. Trous de couverture connus

Honnête sur l'état actuel — la logique métier est bien couverte (use cases testés un par
un), mais quelques **routes HTTP** s'appuient sur des use cases testés en unitaire sans
test d'intégration de la route elle-même :

| Zone | État | Note |
|---|---|---|
| Routes `games.py` (`/games/start`, `/games/{id}/events`, `/finish`, `/{id}`) | use cases testés ✅ / route HTTP ❌ | logique couverte, câblage FastAPI non testé de bout en bout |
| Routes `rooms.py` (`/rooms`, `/rooms/{code}/join`, `/rooms/list`) | use cases testés ✅ / route HTTP ❌ | idem |
| Scénarios d'erreur réseau MQTT / WS | partiels | le happy-path et le routing sont couverts, pas les pannes réseau |

Ces trous sont **à faible risque** (le cœur est testé), mais ce sont les premiers candidats
si on veut monter la couverture — voir les routes déjà testées (`test_players_http.py`,
`test_scores_http.py`) comme modèle à suivre.

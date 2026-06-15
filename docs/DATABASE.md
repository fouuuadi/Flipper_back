# Database — Flipper Backend

> Schéma **PostgreSQL 16** (asyncpg, SQL brut, pas d'ORM) et invariants de persistance.
> Source de vérité : les scripts `db/init/*.sql` (appliqués dans l'ordre numérique au
> premier démarrage du container `postgres`).
>
> Pour le stockage **éphémère** (Redis) pendant la partie, voir §4. Pour le flux d'écriture,
> voir [`WORKFLOW.md`](./WORKFLOW.md).

---

## 1. Invariant central — écriture DB en fin de partie uniquement

Le découpage clé de l'archi :

| Pendant la partie | Fin de partie |
|---|---|
| **Redis** : score, vies, combo, statut (Hash) + events bruts (List) | **PostgreSQL** : flush atomique via `POST /scores` |
| volatile, TTL 30 min sliding | persistant |

⇒ **Aucune écriture en DB pendant le jeu.** La DB ne contient que des parties **terminées**
(via `POST /scores`) ou les données du flow legacy `rooms`/`games`. C'est ce qui permet le
temps réel sans marteler la base.

> Exception : le flow legacy `/games/*` écrit directement en DB (pré-migration). Il
> coexiste mais n'est pas le chemin nominal.

---

## 2. Schéma relationnel

```
players ──1:N──> games <──N:1── rooms
                   │
                   └──1:N──> game_events
```

### `players` — `db/init/001_create_players.sql`
```sql
CREATE TABLE players (
    id         SERIAL PRIMARY KEY,
    pseudo     VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
- `pseudo` est **UNIQUE** → c'est la clé d'idempotence. Upsert applicatif = `SELECT id WHERE pseudo=$1`, sinon `INSERT ... RETURNING id` (pas de `ON CONFLICT`, cf. `game_repository._upsert_player`).
- Format stocké : `XXX#YYYYY` (cf. `domain/pseudo.py`).

### `rooms` — `db/init/002_create_rooms.sql`
```sql
CREATE TABLE rooms (
    id         SERIAL PRIMARY KEY,
    code       VARCHAR(10) NOT NULL UNIQUE,
    mode       VARCHAR(20) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
- `code` **UNIQUE** (identifiant public de la room).
- `mode` : `solo` | `1v1`. `status` : `waiting` | … (flow legacy rooms).

### `games` — `db/init/003_create_games.sql` (+ `005` ALTER)
```sql
CREATE TABLE games (
    id          SERIAL PRIMARY KEY,
    match_id    INTEGER,                       -- réservé (voir note)
    player_id   INTEGER NOT NULL REFERENCES players(id),
    room_id     INTEGER     REFERENCES rooms(id),  -- nullable depuis 005 (solo)
    mode        VARCHAR(20) NOT NULL,          -- 'solo' | '1v1'
    score       INTEGER NOT NULL DEFAULT 0,
    status      VARCHAR(20) NOT NULL DEFAULT 'playing',  -- 'playing' | 'finished'
    started_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP                       -- NULL tant que non terminée
);
```
- **`005_alter_games_room_id_nullable.sql`** rend `room_id` nullable : une session **solo**
  n'est liée à aucune room (`room_id = NULL`).
- Au flush `POST /scores`, une game est insérée directement avec `status='finished'` et
  `finished_at` renseigné.
- Le leaderboard et l'historique ne comptent que `status='finished'`.

> ⚠️ **`match_id`** : colonne présente (sans FK) mais **aucune table `matches`** n'existe
> dans `db/init/`. L'entité `domain/match.py` existe côté code mais n'est pas persistée.
> Colonne réservée pour un futur regroupement de games en match 1v1 — non utilisée à ce jour.

### `game_events` — `db/init/004_create_game_events.sql`
```sql
CREATE TABLE game_events (
    id         SERIAL PRIMARY KEY,
    game_id    INTEGER NOT NULL REFERENCES games(id),
    type       VARCHAR(50) NOT NULL,
    points     INTEGER NOT NULL DEFAULT 0,
    occured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
- Insérés **en batch** au flush (tous les events accumulés en Redis pendant la partie).
- `type` : libellé de l'event (bumper hit, bonus, ball lost…).

---

## 3. Conventions & contraintes techniques

- **Numérotation** `db/init/NNN_description.sql` : appliqués dans l'ordre croissant. Pour
  une nouvelle migration → numéro suivant (`006_…`), jamais réécrire un script existant
  (la DB de prod ne rejoue pas les anciens).
- **`SERIAL`** pour les PK auto-incrémentées (équivaut à `IDENTITY`).
- **`TIMESTAMP` sans timezone** : asyncpg n'accepte **pas** de `datetime` tz-aware sur ces
  colonnes. Les repos strippent la tzinfo avant insert (`dt.replace(tzinfo=None)`). En tenir
  compte pour toute nouvelle colonne temporelle.
- **Placeholders asyncpg** : `$1, $2, …` (pas `%s`). `RETURNING` pour récupérer les ids générés.
- **Transactions** : multi-tables via le pattern Unit of Work (`PgUnitOfWork`, cf.
  `ARCHITECTURE.md`). Le flush `POST /scores` et `POST /games/start` sont atomiques
  (rollback complet si une étape échoue).

---

## 4. Stockage éphémère Redis (hors DB, pour contexte)

Pas en PostgreSQL, mais c'est l'autre moitié du modèle de données.

| Clé Redis | Type | Contenu | TTL |
|---|---|---|---|
| `session:{session_id}` | Hash | `session_id, pseudo, score, lives, combo, status, room_code, mode, created_at` | 30 min sliding |
| `events:{session_id}` | List | events MQTT bruts accumulés pendant la partie | 30 min sliding |

Au flush `POST /scores` : ces deux clés sont **lues** (→ insert PostgreSQL) puis **supprimées**
après commit DB réussi. Si la transaction DB échoue, Redis n'est pas nettoyé → le client peut
retenter.

---

## 5. Repositories (couche infrastructure)

Implémentations asyncpg dans `app/infrastructure/db/` (toutes acceptent un `Pool` ou une
`Connection` sous Unit of Work) :

| Repo | Table | Port |
|---|---|---|
| `PgPlayerRepository` | `players` | `PlayerRepository` |
| `PgRoomRepository` | `rooms` | `RoomRepository` |
| `PgGameRepository` | `games` (+ flush multi-tables) | `GameRepository` |
| `PgGameEventRepository` | `game_events` | `GameEventRepository` |

Mapping `row → entity` : `app/infrastructure/db/mappers/`.

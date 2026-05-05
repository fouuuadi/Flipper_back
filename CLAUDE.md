# CLAUDE.md — Flipper Backend

## WHY
Flipper est le backend d'un jeu de flipper multijoueur développé dans le cadre d'un projet final à HETIC.
Il gère les sessions de jeu, les scores et la communication temps réel entre joueurs.

---

## WHAT

API backend pour un jeu de flipper en modes Solo et 1v1, exposant :
- Des endpoints HTTP REST (health check, root)
- Un endpoint WebSocket temps réel (`/ws`) pour les événements de jeu
- Une connexion asynchrone à MySQL pour la persistance

**Structure des dossiers :**
```
app/
├── domain/         → Entités métier Pydantic (Player, Room, Game, Match, GameEvent)
├── infrastructure/ → Connexion DB (MySQL async pool avec retry)
└── transport/
    ├── http/       → Routes REST (root, health)
    └── ws/         → WebSocket handler + Hub de diffusion
tests/              → Tests pytest (HTTP + WebSocket)
.github/workflows/  → CI (lint, test, build) + CD (build.yml → GHCR)
```

**Entités principales :** `Player` → crée une `Room` → génère un `Game` (ou `Match` en 1v1) → émet des `GameEvent`

---

## HOW

**Langage & runtime :** Python 3.12

**Conventions de nommage :**
- `snake_case` pour variables, fonctions, modules
- `PascalCase` pour classes et enums Pydantic
- `UPPER_CASE` pour les constantes et valeurs d'enum

**Commits :** Conventional Commits obligatoires
- `feat(scope):`, `fix(scope):`, `refactor(scope):`, `chore(scope):`, `ci(scope):`

**Tests :** `pytest tests/ -v` — tout nouveau code doit être testé

**Linting :** `ruff check .` — aucun warning toléré en CI

**Variables d'environnement :** copier `.env.exemple` → `.env`, ne jamais committer `.env`

**Démarrage local :**
```bash
docker compose up --build   # Lance MySQL + phpMyAdmin + backend
```

**Stack :**
- FastAPI 0.115.12 + Uvicorn (ASGI)
- aiomysql (connexion async MySQL)
- Pydantic v2 (validation des données)
- WebSockets via FastAPI
- pytest + pytest-asyncio

---

## RÈGLES

- **NE JAMAIS** committer le fichier `.env` ou des secrets en clair
- **NE JAMAIS** utiliser du code synchrone/bloquant (tout doit être `async/await`)
- **NE JAMAIS** mettre de logique métier dans la couche `transport/` (HTTP ou WS)
- **NE JAMAIS** accéder à la DB directement depuis `domain/` — passer par `infrastructure/`
- **NE JAMAIS** pusher directement sur `main` — passer par une PR
- **NE JAMAIS** ignorer un échec Trivy (`CRITICAL`) lors du build CI
- **NE PAS** ajouter de dépendances sans les épingler avec une version fixe dans `requirements.txt`

---

## ARCHITECTURE

**Décisions majeures :**

1. **Clean Architecture en 3 couches** : `domain` → `infrastructure` → `transport`
   Les couches supérieures ne connaissent pas les couches inférieures.

2. **Tout est async** : FastAPI + aiomysql + WebSockets — aucun appel bloquant autorisé.

3. **Hub Pattern pour WebSocket** : Un hub centralisé (`transport/ws/hub.py`) gère tous les clients connectés et le broadcast. Pas de communication directe entre clients.

4. **MySQL comme seule source de vérité** : Pas de cache, pas de stockage en mémoire pour les données persistantes.

5. **Docker-first** : L'application est conçue pour tourner dans Docker. `docker compose up` est le point d'entrée standard.

6. **CI/CD GitHub Actions** :
   - `ci.yml` : lint + tests + build à chaque push/PR
   - `build.yml` : build + scan Trivy + push vers GHCR (`ghcr.io/fouuuadi/flipper-backend`) sur merge dans `main`
   - `update-center.yml` : met à jour automatiquement le submodule dans `Flipper_Center`

7. **Ce projet est un submodule** de `fouuuadi/Flipper_Center` — toute modification de `main` déclenche une mise à jour automatique du monorepo parent.

---
marp: true
theme: default
paginate: true
title: Flipper Backend — Soutenance
---

<!--
Support de présentation orale (format Marp).
Lisible tel quel, ET exportable en slides :
  - VSCode : extension "Marp for VS Code" → Export (PDF / PPTX / HTML)
  - CLI    : npx @marp-team/marp-cli docs/PRESENTATION.md --pdf
Les blocs <!-- ... --> en début de slide sont les notes orateur (vue présentateur).
-->

# 🎮 Flipper — Backend

### Un flipper physique connecté, scores en temps réel

Architecture temps réel · IoT · Clean Architecture

<!--
Pitch d'ouverture : on a connecté un vrai flipper physique à un backend qui suit le score
en direct et persiste les parties. Présenter l'équipe + le périmètre (backend uniquement).
-->

---

## Le problème

Un **flipper physique** envoie des événements (bumpers, perte de bille…).
Il faut :

- afficher le **score en temps réel** sur un écran / une app
- supporter le **multijoueur** (solo & 1v1)
- garder un **historique** + un **classement** des parties

**Le défi technique** : du temps réel fiable, sans écrouler la base de données.

<!--
Insister sur la tension : événements très fréquents (chaque bumper) vs base de données
qui n'aime pas être écrite des centaines de fois par seconde. C'est ce qui justifie toute
l'architecture qui suit.
-->

---

## Vue d'ensemble

```
  Flipper physique          Client (web/app)
   (capteurs IoT)                  │
        │ MQTT                     │ HTTP + WebSocket
        ▼                          ▼
   ┌──────────────────────────────────────────┐
   │            BACKEND (FastAPI)              │
   │                                           │
   │   MQTT ──► Redis (live) ──► WebSocket     │
   │                  │                        │
   │                  └──► PostgreSQL (fin)    │
   └──────────────────────────────────────────┘
```

3 canaux : **MQTT** (entrée IoT) · **WebSocket** (sortie temps réel) · **HTTP** (commandes)

<!--
Donner la vue à 10 000 pieds avant de plonger. Les flèches racontent déjà l'histoire :
l'IoT entre par MQTT, le live vit dans Redis, le client est notifié par WebSocket,
et seule la fin de partie touche PostgreSQL.
-->

---

## Le flow d'une partie — 3 actes

**Acte 1 — Avant (HTTP)**
`POST /sessions` → crée une session **éphémère en Redis** (score 0, pseudo). *Pas de DB.*

**Acte 2 — Pendant (MQTT → Redis → WebSocket)**
Le flipper publie sur MQTT → le backend met à jour Redis → **broadcast WebSocket** au client.
`score:update`, `ball:lost`, `game:over`…

**Acte 3 — Fin (HTTP, seule écriture DB)**
`POST /scores` → flush **atomique** Redis → PostgreSQL (Player + Game + events), puis Redis nettoyé.

<!--
C'est LE cœur de la démo. Bien marteler "Acte 2 ne touche jamais la base". Une partie =
des centaines d'events en Redis, et UNE seule transaction en DB à la fin.
-->

---

## 3 choix techniques (et pourquoi)

| Choix | Pourquoi |
|---|---|
| **Redis** pendant la partie | Score live en mémoire → latence minimale, pas de spam DB |
| **MQTT** (Mosquitto) | Standard IoT : le hardware publie, le backend s'abonne, découplé |
| **Écriture DB en fin uniquement** | La base ne stocke que des parties **terminées** → perf + cohérence |

> Bonus : **session éphémère** (TTL 30 min) ≠ **données persistées**. Séparation claire.

<!--
Chaque ligne = une question probable du jury. Pourquoi pas tout en base ? → spam d'écritures.
Pourquoi MQTT et pas du HTTP depuis le flipper ? → standard IoT, pub/sub, découplage.
-->

---

## Clean Architecture — 4 couches

```
transport/      → HTTP routes, WebSocket   (le plus externe)
   ▼
usecase/        → orchestration métier
   ▼
infrastructure/ → asyncpg, redis, mqtt
   ▼
domain/         → entités + interfaces      (le plus interne, zéro dépendance)
```

**Règle d'or** : les dépendances pointent toujours vers l'intérieur.

➡️ Le métier est **testable sans I/O**, et on a migré **MySQL → PostgreSQL sans toucher au métier**.

<!--
Argument fort : la migration de base de données n'a impacté QUE la couche infrastructure.
C'est la preuve concrète que la Clean Archi paie. Mentionner les "ports" (interfaces) qui
permettent l'inversion de dépendance.
-->

---

## Qualité & industrialisation

- ✅ **261 tests** (unit + intégration : PostgreSQL, Redis, MQTT réels)
- ✅ **import-linter** : 4 contracts d'architecture vérifiés en CI (impossible de casser les couches)
- ✅ **CI/CD** GitHub Actions → image Docker (GHCR), scan sécurité Trivy
- ✅ **Docker Compose** : toute la stack en une commande
- ✅ **Logs JSON structurés** + `X-Request-ID` (observabilité)

<!--
Montrer que ce n'est pas un POC : tests, CI, sécurité, conteneurisation. Le import-linter
est un point différenciant : l'architecture est garantie par la CI, pas juste par discipline.
-->

---

## Démo

```bash
# 1. Créer une session
curl -X POST localhost:8080/sessions -d '{"pseudo":"ABC","mode":"solo"}'

# 2. Écouter le temps réel
wscat -c "ws://localhost:8080/ws?session_id=XYZ"

# 3. Simuler le flipper (MQTT)
mosquitto_pub -t flipper/bumper/hit -m '{"bumperId":1,"points":100,"sessionId":"XYZ"}'
#   → le WebSocket affiche  score:update { score: 100 }

# 4. Fin de partie → persistance
curl -X POST localhost:8080/scores -d '{"sessionId":"XYZ"}'
```

<!--
Scénario live. Avoir les 3 terminaux prêts (serveur, wscat, mosquitto_pub). Si pas de live,
montrer une capture. C'est le moment le plus parlant : on VOIT le score monter en temps réel.
-->

---

## État & suites

**Fait** ✅
Sessions Redis · Bridge MQTT · WebSocket temps réel · Flush DB atomique ·
Leaderboard & historique · Migration PostgreSQL · Unit of Work · Logs JSON

**À venir** 📌
EventBus interne · Matchmaking 1v1 · WebSocket broadcast par room

**Docs techniques** : `ARCHITECTURE.md` · `API.md` · `DATABASE.md` · `WORKFLOW.md`

<!--
Conclure sur la maturité du projet et une roadmap crédible. Renvoyer aux docs pour les
questions de détail. Remercier + ouvrir les questions.
-->

---

# Merci 🙏

### Questions ?


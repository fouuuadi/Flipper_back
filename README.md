# Backend - Flipper

## Player Repository Setup & Tests

### 1) Installer les dépendances

Depuis `back/` :

```bash
pip install -r requirements.txt
```

### 2) Démarrer la base de données (Docker)

Depuis `back/` :

```bash
docker compose up -d
docker compose ps
```

Voir les logs d'initialisation :
```bash
docker compose logs db
```



### 3) Lancer les tests

Depuis `back/` :

```bash
pytest tests/test_player_repository.py -v
```

Attendu :
- `test_create_and_get_by_id` → `PASSED`
- `test_create_and_get_by_pseudo` → `PASSED`
- `test_duplicate_pseudo_raises_error` → `PASSED`
- `test_get_nonexistent_player` → `PASSED`
- `test_multiple_players` → `PASSED`



### Notes

- **Base de données persistante** : Le volume `db_data` conserve les données entre les redémarrages
- **Réinitialiser complètement** : `docker compose down -v && docker compose up -d`
- **Fichier .env requis** : Assurez-vous que `DB_USER`, `DB_PASSWORD`, `MYSQL_DATABASE` sont définis

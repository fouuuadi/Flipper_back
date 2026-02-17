# Gestion Git du projet Flipper

## Base

Créer localement un projet flipper_project dans lequel on relie nos autres repo :

# Clone le front

git clone https://github.com/fouuuadi/Robotique_front.git

Dans le dossier robotique_front/ → tu pousses/pull sur le repo robotique_front.

# Clone le back

git clone https://github.com/fouuuadi/robotique_back.git    

Dans le dossier robotique_back/ → tu pousses/pull sur le repo robotique_back.



## Gestion des branches

- Toujours créer une branche avec un nom clair pour chaque fonctionnalité (ex : git checkout -b feature/ajout-backglass
)
- **Ne jamais travailler directement sur la branche principale** `main`
- **Créer une Pull Request** sur GitHub quand la branche est terminée pour demander une relecture avant fusion.


## Gestion avec GitHub Projects

Nous utilisons **GitHub Projects** pour organiser, suivre et visualiser l’avancement du travail en équipe.  
Notre tableau "Robotique Project Final" fonctionne par colonnes représentant les étapes de chaque tâche.

### Fonctionnement du tableau

- **Backlog** :  
  Tâches identifiées mais pas encore planifiées.

- **To Do** :  
  Tâches prêtes à démarrer. Chaque membre peut y prendre une tâche à réaliser.

- **In progress** :  
  Tâches actuellement en cours de développement (prises en charge par quelqu’un).

- **In review** :  
  Tâches terminées côté code, en attente de relecture ou de validation par un autre membre.

- **Done** :  
  Tâches validées, relues et intégrées au projet.

- **Bugs** :  
  Liste de tous les bugs à corriger, pour ne rien oublier et les prioriser.



### Méthode d'utilisation

1. Toute nouvelle fonctionnalité ou problème à résoudre est ajoutée comme un item dans le tableau, dans la colonne adaptée.
2. Chacun choisi une tâche "To Do" et la fait passer en "In progress" quand il commence à la traiter.
3. Une fois la tâche finie, elle passe en "In review" pour vérification par un autre membre.
4. Si tout est bon, elle passe en "Done".
5. Les bugs détectés vont dans "Bugs" puis suivent le même processus.



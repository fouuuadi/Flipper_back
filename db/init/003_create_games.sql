CREATE TABLE games (
    id int AUTO_INCREMENT PRIMARY KEY,
    match_id int,
    player_id int NOT NULL,
    mode VARCHAR(20) NOT NULL,
    score int NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'playing',
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    FOREIGN KEY (player_id) REFERENCES players(id),
);
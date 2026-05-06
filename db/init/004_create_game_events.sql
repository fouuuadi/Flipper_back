CREATE TABLE game_events (
    id int AUTO_INCREMENT PRIMARY KEY,
    game_id int NOT NULL,
    type VARCHAR(50) NOT NULL,
    points int NOT NULL DEFAULT 0,
    occured_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
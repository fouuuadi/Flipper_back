CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    match_id INTEGER,
    player_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    mode VARCHAR(20) NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'playing',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

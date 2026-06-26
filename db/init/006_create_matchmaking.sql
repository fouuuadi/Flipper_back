CREATE TABLE matchmaking (
    id SERIAL PRIMARY KEY,
    player1_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    player2_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    mode VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_matchmaking_status_mode ON matchmaking(status, mode);

CREATE TABLE matchmaking (
    id SERIAL PRIMARY KEY,
    player1_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    player2_id INTEGER REFERENCES players(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL,
    mode VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_matchmaking_status_mode ON matchmaking(status, mode);

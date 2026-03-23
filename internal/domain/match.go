package domain

import "time"

type Match struct {
	ID           int64     `json:"id"`
	Player1ID    int64     `json:"player1_id"`
	Player2ID    int64     `json:"player2_id"`
	Player1Score int64     `json:"player1_score"`
	Player2Score int64     `json:"player2_score"`
	WinnerID     *int64    `json:"winner_id,omitempty"`
	PlayedAt     time.Time `json:"played_at"`
}

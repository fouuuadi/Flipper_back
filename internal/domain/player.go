package domain

import "time"

type Player struct {
	ID        int64     `json:"id"`
	Pseudo    string    `json:"pseudo"`
	CreatedAt time.Time `json:"created_at"`
}

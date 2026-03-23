package domain

import "time"

type RoomStatus string

const (
	RoomStatusWaiting  RoomStatus = "waiting"
	RoomStatusPlaying  RoomStatus = "playing"
	RoomStatusFinished RoomStatus = "finished"
)

type Room struct {
	ID        int64      `json:"id"`
	Code      string     `json:"code"`
	Mode      GameMode   `json:"mode"`
	Status    RoomStatus `json:"status"`
	CreatedAt time.Time  `json:"created_at"`
}

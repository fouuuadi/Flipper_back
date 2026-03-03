package ws

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

type Message struct {
	Type      string          `json:"type"`
	Payload   json.RawMessage `json:"payload,omitempty"`
	Timestamp int64           `json:"timestamp,omitempty"`
}

// Upgrader Gorilla: convertit HTTP -> WebSocket
var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// ServeWS gère: upgrade + logs + echo JSON
func ServeWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[ws] upgrade error: %v", err)
		return
	}
	defer func() {
		_ = conn.Close()
		log.Printf("[ws] disconnected: remote=%s", r.RemoteAddr)
	}()

	log.Printf("[ws] connected: remote=%s", r.RemoteAddr)

	for {
		msgType, data, err := conn.ReadMessage()
		if err != nil {
			log.Printf("[ws] read error: %v", err)
			return
		}

		log.Printf("[ws] received %d bytes", len(data))


		var incoming Message
		if err := json.Unmarshal(data, &incoming); err == nil {
			if incoming.Timestamp == 0 {
				incoming.Timestamp = time.Now().UnixMilli()
			}
			out, _ := json.Marshal(incoming)
			if err := conn.WriteMessage(msgType, out); err != nil {
				log.Printf("[ws] write error: %v", err)
				return
			}
			continue
		}

		// Fallback: echo brut
		if err := conn.WriteMessage(msgType, data); err != nil {
			log.Printf("[ws] write error: %v", err)
			return
		}
	}
}
// handler.go implémente le gestionnaire HTTP pour les connexions WebSocket, permettant aux clients de se connecter, d'envoyer des messages et de recevoir des diffusions de messages de la part du hub.

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

type Handler struct {
	Hub      *Hub
	Upgrader websocket.Upgrader
	Logger   *log.Logger
}

func NewHandler(hub *Hub, logger *log.Logger) *Handler {
	return &Handler{
		Hub: hub,
		Upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		},
		Logger: logger,
	}
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	conn, err := h.Upgrader.Upgrade(w, r, nil)
	if err != nil {
		h.printf("[ws] upgrade error: %v", err)
		return
	}

	h.Hub.Add(conn)

	defer func() {
		h.Hub.Remove(conn)
		_ = conn.Close()
		h.printf("[ws] disconnected: remote=%s (clients=%d)", r.RemoteAddr, h.Hub.Count())
	}()

	h.printf("[ws] connected: remote=%s (clients=%d)", r.RemoteAddr, h.Hub.Count())

	for {
		msgType, data, err := conn.ReadMessage()
		if err != nil {
			h.printf("[ws] read error: %v", err)
			return
		}
		h.printf("[ws] received %d bytes", len(data))

		var incoming Message
		if err := json.Unmarshal(data, &incoming); err == nil {
			if incoming.Timestamp == 0 {
				incoming.Timestamp = time.Now().UnixMilli()
			}
			out, _ := json.Marshal(incoming)
			h.Hub.Broadcast(msgType, out)
			continue
		}

		h.Hub.Broadcast(msgType, data)
	}
}

func (h *Handler) printf(format string, args ...any) {
	if h.Logger == nil {
		return
	}
	h.Logger.Printf(format, args...)
}
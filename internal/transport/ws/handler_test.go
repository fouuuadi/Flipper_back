// handler_test.go contient des tests unitaires pour le gestionnaire WebSocket, vérifiant que les messages envoyés par un client sont correctement diffusés à tous les clients connectés.
package ws

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

func TestWebSocketBroadcastToTwoClients(t *testing.T) {


	hub := NewHub()
	h := NewHandler(hub, nil) 

	mux := http.NewServeMux()
	mux.Handle("/ws", h)

	srv := httptest.NewServer(mux)
	defer srv.Close()

	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http") + "/ws"

	// Connecte 2 clients
	c1, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("dial c1: %v", err)
	}
	defer c1.Close()

	c2, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("dial c2: %v", err)
	}
	defer c2.Close()

	_ = c1.SetReadDeadline(time.Now().Add(2 * time.Second))
	_ = c2.SetReadDeadline(time.Now().Add(2 * time.Second))

	// c1 envoie un message
	in := Message{
		Type:    "input",
		Payload: json.RawMessage(`{"key":"LEFT"}`),
	}
	inBytes, _ := json.Marshal(in)

	if err := c1.WriteMessage(websocket.TextMessage, inBytes); err != nil {
		t.Fatalf("c1 write: %v", err)
	}

	// Les 2 doivent recevoir un message
	_, b1, err := c1.ReadMessage()
	if err != nil {
		t.Fatalf("c1 read: %v", err)
	}
	_, b2, err := c2.ReadMessage()
	if err != nil {
		t.Fatalf("c2 read: %v", err)
	}

	var m1, m2 Message
	if err := json.Unmarshal(b1, &m1); err != nil {
		t.Fatalf("unmarshal c1 msg: %v", err)
	}
	if err := json.Unmarshal(b2, &m2); err != nil {
		t.Fatalf("unmarshal c2 msg: %v", err)
	}

	if m1.Type != "input" || m2.Type != "input" {
		t.Fatalf("expected type=input for both, got c1=%q c2=%q", m1.Type, m2.Type)
	}
	if string(m1.Payload) != `{"key":"LEFT"}` || string(m2.Payload) != `{"key":"LEFT"}` {
		t.Fatalf("unexpected payloads: c1=%s c2=%s", string(m1.Payload), string(m2.Payload))
	}
	if m1.Timestamp == 0 || m2.Timestamp == 0 {
		t.Fatalf("expected timestamps set, got c1=%d c2=%d", m1.Timestamp, m2.Timestamp)
	}
}
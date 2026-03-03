// test fonctionnel echo websocket

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

func TestWebSocketEchoJSON(t *testing.T) {
	// 1) Serveur HTTP de test avec la route /ws branchée sur ServeWS
	mux := http.NewServeMux()
	mux.HandleFunc("/ws", ServeWS)

	srv := httptest.NewServer(mux)
	defer srv.Close()

	// 2) Convertir URL HTTP -> URL WS
	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http") + "/ws"

	// 3) Connexion WebSocket
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("dial websocket: %v", err)
	}
	defer conn.Close()

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))


	in := Message{
		Type:    "echo",
		Payload: json.RawMessage(`{"hello":"world"}`),
	}
	inBytes, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal input: %v", err)
	}

	if err := conn.WriteMessage(websocket.TextMessage, inBytes); err != nil {
		t.Fatalf("write message: %v", err)
	}

	_, outBytes, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("read message: %v", err)
	}

	var out Message
	if err := json.Unmarshal(outBytes, &out); err != nil {
		t.Fatalf("unmarshal output: %v (raw=%s)", err, string(outBytes))
	}

	if out.Type != "echo" {
		t.Fatalf("expected type=echo, got %q", out.Type)
	}
	if string(out.Payload) != `{"hello":"world"}` {
		t.Fatalf("expected payload=%s, got %s", `{"hello":"world"}`, string(out.Payload))
	}
	if out.Timestamp == 0 {
		t.Fatalf("expected timestamp to be set, got 0 (raw=%s)", string(outBytes))
	}
}
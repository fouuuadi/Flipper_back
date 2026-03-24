package ws

import (
	"log"
	"net/http"
)

type Deps struct {
	Hub    *Hub
	Logger *log.Logger
}

func RegisterRoutes(mux *http.ServeMux, deps Deps) {
	mux.Handle("/ws", NewHandler(deps.Hub, deps.Logger))
}
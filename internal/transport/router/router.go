package router

import (
	"log"
	"net/http"

	httptransport "github.com/fouuuadi/Flipper_back/internal/transport/http"
	"github.com/fouuuadi/Flipper_back/internal/transport/ws"
)

type Deps struct {
	Logger *log.Logger
	WSHub  *ws.Hub
}

func Register(mux *http.ServeMux, deps Deps) {
	// HTTP routes
	httptransport.RegisterRoutes(mux)

	// WS routes
	ws.RegisterRoutes(mux, ws.Deps{
		Hub:    deps.WSHub,
		Logger: deps.Logger,
	})
}


package httptransport

import "net/http"

func RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/", RootHandler)
	mux.HandleFunc("/health", HealthHandler)
}
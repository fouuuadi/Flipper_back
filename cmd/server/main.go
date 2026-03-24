package main


import (
	"fmt"
	"net/http"
	"os"
	"log"


	_ "github.com/go-sql-driver/mysql"
	"github.com/joho/godotenv"

	"github.com/fouuuadi/Flipper_back/internal/infrastructure/db"
	"github.com/fouuuadi/Flipper_back/internal/transport/router"
	"github.com/fouuuadi/Flipper_back/internal/transport/ws"

)

func main() {
	// Load env
	_ = godotenv.Load()

	// Connect DB (wait + retry inside)
	database, err := db.NewMySQLConnection()
	if err != nil {
		panic(err)
	}
	defer database.Close()

	// Port config
	port := ":" + os.Getenv("APP_PORT")
	if port == ":" {
		port = ":8080"
	}

	logger := log.Default()
	mux := http.NewServeMux()

	// Deps
	wsHub := ws.NewHub()

	// Register all routes (HTTP + WS)
	router.Register(mux, router.Deps{
		Logger: logger,
		WSHub:  wsHub,
	})

	fmt.Println("Server started on http://localhost" + port)

	if err := http.ListenAndServe(port, mux); err != nil {
		panic(err)
	}
}

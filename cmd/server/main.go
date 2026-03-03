package main


//fmt est un utilitaire pour afficher du text
// net/http est un bibliothèque standard pour créer un serveur Http
import (
	"fmt"
	"net/http"
	"os"


	_ "github.com/go-sql-driver/mysql"
	"github.com/joho/godotenv"
	"github.com/fouuuadi/Flipper_back/internal/infrastructure/db"
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

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request){
		fmt.Fprintln(w, "Flipper backend running")
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprintln(w, "OK")
	})

	http.HandleFunc("/ws", ws.ServeWS)

	fmt.Println("Server started on http://localhost" + port)

	if err := http.ListenAndServe(port, nil); err != nil {
		panic(err)
	}
}

package main


//fmt est un utilitaire pour afficher du text
// net/http est un bibliothèque standard pour créer un serveur Http
import(
	"fmt"
	"net/http"
)

func main() {
	port := ":8000"

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request){
		fmt.Fprintln(w, "Flipper backend running")
	})

	fmt.Println("Server started on http://localhost" + port)

	if err := http.ListenAndServe(port, nil); err != nil {
		panic(err)
	}
}

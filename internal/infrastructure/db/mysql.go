package db

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

func NewMySQLConnection() (*sql.DB, error) {
	host := os.Getenv("DB_HOST")
	port := os.Getenv("DB_PORT")
	name := os.Getenv("DB_NAME")
	user := os.Getenv("DB_USER")
	password := os.Getenv("DB_PASSWORD")

	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true",
		user, password, host, port, name,
	)

	var database *sql.DB
	var err error

	for i := 1; i <= 10; i++ {
		database, err = sql.Open("mysql", dsn)
		if err == nil {
			err = database.Ping()
		}

		if err == nil {
			log.Println("✅ Connected to MySQL")
			return database, nil
		}

		log.Printf("⏳ Waiting for MySQL... attempt %d/10\n", i)
		time.Sleep(3 * time.Second)
	}

	return nil, fmt.Errorf("could not connect to MySQL: %w", err)
}

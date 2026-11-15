package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"web/internal/handler"
	"web/internal/service"
	"web/internal/db/postgres"
	"github.com/gorilla/mux"
	"web/internal/integrations"

    _ "github.com/jackc/pgx/v5/stdlib"

    "database/sql"

	"github.com/pressly/goose/v3"
)

func main() {
	_, cancel := context.WithCancel(context.Background())
	defer cancel()

	dsn := "postgres://myuser:mypassword@postgres:5432/mydb?sslmode=disable"
	pool, err := postgres.InitPool(context.Background(), dsn)
	if err != nil {
		log.Fatalf("Ошибка при инициализации пула соединений с базой данных: %v", err)
	}


	if err := goose.SetDialect("postgres"); err != nil {
		log.Fatalf("Ошибка установки диалекта goose: %v", err)
	}

	migrationsPath := "/app/migrations"

	db, err := sql.Open("pgx", dsn)
	if err != nil {
		log.Fatalf("Ошибка подключения для миграций: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatalf("Ошибка проверки подключения к БД: %v", err)
	}

	if err := goose.SetDialect("postgres"); err != nil {
		log.Fatalf("Ошибка установки диалекта: %v", err)
	}

	if err := goose.Up(db, migrationsPath); err != nil {
		log.Fatalf("Ошибка выполнения миграций: %v", err)
	}

	log.Println("Миграции успешно применены!")
	rag := integrations.NewRag("http://ai-service:8000", nil)
	chatRepo := postgres.NewChatRepository(pool)
	messageRepo := postgres.NewMessageRepository(pool)
	chatService := service.NewChatService(chatRepo, rag, messageRepo)
	profileRepo := postgres.NewProfileRepository(pool)
	profileService := service.NewProfileService(profileRepo)
	chatHandler := handler.NewChatHandler(chatService, profileService)

	r := mux.NewRouter()

	r.HandleFunc("/message", chatHandler.ProcessMessage).Methods(http.MethodPost)
	r.HandleFunc("/profile", chatHandler.CreateProfile).Methods(http.MethodPost)
	r.HandleFunc("/chat", chatHandler.CreateChat).Methods(http.MethodPost)

	r.HandleFunc("/chat", chatHandler.GetChatHistory).Methods(http.MethodGet)

	server := &http.Server{
		Addr:    ":8080",
		Handler: r,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Println("Сервер запущен на порту :8080")
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("Ошибка сервера: %v", err)
		}
	}()

	<-stop
	log.Println("Получен сигнал завершения, останавливаемся...")

	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("Ошибка при плавном закрытии сервера: %v", err)
	}

	log.Println("Приложение успешно остановлено")
}

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
)

func main() {
	_, cancel := context.WithCancel(context.Background())
	defer cancel()

	dsn := "postgres://myuser:mypassword@localhost:5432/mydb?sslmode=disable"
	pool, err := postgres.InitPool(context.Background(), dsn)
	if err != nil {
		log.Fatalf("Ошибка при инициализации пула соединений с базой данных: %v", err)
	}

	chatService := service.NewChatService()
	chatHandler := handler.NewChatHandler(chatService)

	r := mux.NewRouter()

	r.HandleFunc("/message", chatHandler.GetMessage).Methods(http.MethodPost)
	r.HandleFunc("/profile", chatHandler.CreateProfile).Methods(http.MethodPost)

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

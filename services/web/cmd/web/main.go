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
)

func main() {
	_, cancel := context.WithCancel(context.Background())
	defer cancel()

	chatService := service.NewChatService()
	chatHandler := handler.NewChatHandler(chatService)

	mux := http.NewServeMux()
	mux.HandleFunc("/message", chatHandler.GetMessage) 

	server := &http.Server{
		Addr:    ":8080",
		Handler: mux,
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

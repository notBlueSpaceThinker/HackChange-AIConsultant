package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"context"
	"github.com/google/uuid"
)


type ChatService interface {
	ProcessIncomingMessage(ctx context.Context, query string, chatID uuid.UUID) (string, error)
	GetChatHistory(ctx context.Context, chatID uuid.UUID) ([]string, error)
	CreateChat(ctx context.Context, sessionID uuid.UUID) (uuid.UUID, error) 
}


type ChatHandler struct {
	ChatService ChatService
	ProfileService ProfileService
}

func NewChatHandler(service ChatService, profileService ProfileService) *ChatHandler {
	return &ChatHandler{
		ChatService: service,
		ProfileService: profileService,	
	}
}


type getMessageRequest struct{
	Query string `json:"query"`
	ChatID string `json:"chat_id"`
}


func (o *ChatHandler) ProcessMessage(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("invalid request body: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var req getMessageRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, fmt.Sprintf("invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	chatID, err := uuid.Parse(req.ChatID)
	if err != nil {
		http.Error(w, "invalid chat ID", http.StatusBadRequest)
		return
	}

	response, err := o.ChatService.ProcessIncomingMessage(r.Context(), req.Query, chatID)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to process message: %v", err.Error()), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"message": response})
}


type getProfileRequest struct {
	SessionID string `json:"session_id"`
	FullName string `json:"full_name"`
	Phone string `json:"phone"`
	Company string `json:"company"`	
}

func (o *ChatHandler) CreateProfile(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	defer r.Body.Close()

	var req getProfileRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, fmt.Sprintf("invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	err = o.ProfileService.CreateProfile(r.Context(), req.SessionID, req.FullName, req.Phone, req.Company)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to create profile: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusCreated)
}

func (o *ChatHandler) GetChatHistory(w http.ResponseWriter, r *http.Request) {
	chatIDStr := r.URL.Query().Get("chat_id")
	if chatIDStr == "" {
		http.Error(w, "chat_id query parameter is required", http.StatusBadRequest)
		return
	}

	chatID, err := uuid.Parse(chatIDStr)
	if err != nil {
		http.Error(w, "invalid chat ID", http.StatusBadRequest)
		return
	}

	history, err := o.ChatService.GetChatHistory(r.Context(), chatID)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to get chat history: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string][]string{"history": history})
}

func (o *ChatHandler) CreateChat(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	defer r.Body.Close()

	var req struct {
		SessionID string `json:"session_id"`
	}

	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, fmt.Sprintf("invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	sessionID, err := uuid.Parse(req.SessionID)
	if err != nil {
		http.Error(w, "invalid session ID", http.StatusBadRequest)
		return
	}

	chatID, err := o.ChatService.CreateChat(r.Context(), sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to create chat: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"chat_id": chatID.String()})
}

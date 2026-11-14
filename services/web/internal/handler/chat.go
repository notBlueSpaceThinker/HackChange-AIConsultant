package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)


type ChatService interface {
	ProcessIncomingMessage(query string) (string, error)
}

type ChatHandler struct {
	service ChatService
}

func NewChatHandler(service ChatService) *ChatHandler {
	return &ChatHandler{service: service}
}


type getMessageRequest struct{
	Query string `json:"query"`
}


func (o *ChatHandler) GetMessage(w http.ResponseWriter, r *http.Request) {
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

	response, err := o.service.ProcessIncomingMessage(req.Query)
	if err != nil {
		http.Error(w, "failed to process message", http.StatusInternalServerError)
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

	err = o.service.CreateProfile(req.SessionID, req.FullName, req.Phone, req.Company)
	if err != nil {
		http.Error(w, "failed to create profile", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusCreated)
}
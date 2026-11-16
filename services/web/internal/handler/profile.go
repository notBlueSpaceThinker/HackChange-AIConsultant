package handler

import (
	"context"
	"net/http"
	"encoding/json"
)

type ProfileService interface {
	CreateProfile(ctx context.Context, sessionID, chatID, fullName, phone, company string) error
}

type ProfileHandler struct {
	service ProfileService
}

func NewProfileHandler(service ProfileService) *ProfileHandler {
	return &ProfileHandler{service: service}
}

type createProfileRequest struct {
	SessionID string `json:"session_id"`
	ChatID    string `json:"chat_id"`
	FullName  string `json:"full_name"`
	Phone     string `json:"phone"`
	Company   string `json:"company"`
}

func (h *ProfileHandler) CreateProfile(w http.ResponseWriter, r *http.Request) error {
	var req createProfileRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		return err
	}

	return h.service.CreateProfile(r.Context(), req.SessionID, req.ChatID, req.FullName, req.Phone, req.Company)
}

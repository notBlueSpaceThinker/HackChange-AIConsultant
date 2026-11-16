package handler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/google/uuid"
	"web/internal/integrations"
	"web/internal/service"
)

type ChatService interface {
	ProcessIncomingMessage(ctx context.Context, query string, chatID uuid.UUID) (*service.RagResponse, error)
	GetChatHistory(ctx context.Context, chatID uuid.UUID) ([]string, error)
	CreateChat(ctx context.Context, sessionID uuid.UUID) (uuid.UUID, error)
	DeleteChat(ctx context.Context, chatID uuid.UUID) error
	GetDocument(ctx context.Context, docID string) (*service.DocumentResp, error)
	ListOperatorChats(ctx context.Context) ([]service.OperatorChatSummary, error)
	GetOperatorChat(ctx context.Context, chatID uuid.UUID) (*service.OperatorChatDetail, error)
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

type messageSourceResponse struct {
	DocID    string  `json:"doc_id"`
	ChunkID  string  `json:"chunk_id"`
	FilePath string  `json:"filepath"`
	Title    string  `json:"title"`
	Score    float64 `json:"score"`
	Text     string  `json:"text"`
}

type messageProfilerResponse struct {
	EmbeddingTime  *float64 `json:"embedding_time"`
	DBSearchTime   *float64 `json:"db_search_time"`
	RerankingTime  *float64 `json:"reranking_time"`
	GenerationTime *float64 `json:"generation_time"`
	RagTime        *float64 `json:"rag_time"`
}

type processMessageResponse struct {
	Message      string                  `json:"message"`
	ReadyForLead bool                    `json:"ready_for_lead"`
	Sources      []messageSourceResponse `json:"sources"`
	Profiler     messageProfilerResponse `json:"profiler"`
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

	msgCtx, cancel := context.WithTimeout(context.Background(), 250*time.Second)
	defer cancel()

	resp, err := o.ChatService.ProcessIncomingMessage(msgCtx, req.Query, chatID)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to process message: %v", err.Error()), http.StatusInternalServerError)
		return
	}

	sources := make([]messageSourceResponse, 0, len(resp.Sources))
	for _, s := range resp.Sources {
		sources = append(sources, messageSourceResponse{
			DocID:    s.DocID,
			ChunkID:  s.ChunkID,
			FilePath: s.FilePath,
			Title:    s.Title,
			Score:    s.Score,
			Text:     s.Text,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(processMessageResponse{
		Message:      resp.Response,
		ReadyForLead: resp.ReadyForLead,
		Sources:      sources,
		Profiler: messageProfilerResponse{
			EmbeddingTime:  resp.Profiler.EmbeddingTime,
			DBSearchTime:   resp.Profiler.DBSearchTime,
			RerankingTime:  resp.Profiler.RerankingTime,
			GenerationTime: resp.Profiler.GenerationTime,
			RagTime:        resp.Profiler.RagTime,
		},
	})
}


type getProfileRequest struct {
	SessionID string `json:"session_id"`
	ChatID    string `json:"chat_id"`
	FullName  string `json:"full_name"`
	Phone     string `json:"phone"`
	Company   string `json:"company"`
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

	if _, err := uuid.Parse(req.SessionID); err != nil {
		http.Error(w, "invalid session ID", http.StatusBadRequest)
		return
	}
	if req.ChatID != "" {
		if _, err := uuid.Parse(req.ChatID); err != nil {
			http.Error(w, "invalid chat ID", http.StatusBadRequest)
			return
		}
	}

	err = o.ProfileService.CreateProfile(r.Context(), req.SessionID, req.ChatID, req.FullName, req.Phone, req.Company)
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

type documentChunkResponse struct {
	ChunkID    string `json:"chunk_id"`
	ChunkIndex int    `json:"chunk_index"`
	Title      string `json:"title"`
	Text       string `json:"text"`
}

type documentResponse struct {
	DocID    string                  `json:"doc_id"`
	FilePath string                  `json:"filepath"`
	Chunks   []documentChunkResponse `json:"chunks"`
}

func (o *ChatHandler) GetDocument(w http.ResponseWriter, r *http.Request) {
	docIDStr := r.URL.Query().Get("doc_id")
	if docIDStr == "" {
		http.Error(w, "doc_id query parameter is required", http.StatusBadRequest)
		return
	}
	if _, err := uuid.Parse(docIDStr); err != nil {
		http.Error(w, "invalid doc_id", http.StatusBadRequest)
		return
	}

	doc, err := o.ChatService.GetDocument(r.Context(), docIDStr)
	if err != nil {
		if errors.Is(err, integrations.ErrDocumentNotFound) {
			http.Error(w, "document not found", http.StatusNotFound)
			return
		}
		http.Error(w, fmt.Sprintf("failed to get document: %v", err), http.StatusInternalServerError)
		return
	}

	chunks := make([]documentChunkResponse, 0, len(doc.Chunks))
	for _, c := range doc.Chunks {
		chunks = append(chunks, documentChunkResponse{
			ChunkID:    c.ChunkID,
			ChunkIndex: c.ChunkIndex,
			Title:      c.Title,
			Text:       c.Text,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(documentResponse{
		DocID:    doc.DocID,
		FilePath: doc.FilePath,
		Chunks:   chunks,
	})
}

func (o *ChatHandler) DeleteChat(w http.ResponseWriter, r *http.Request) {
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

	if err := o.ChatService.DeleteChat(r.Context(), chatID); err != nil {
		http.Error(w, fmt.Sprintf("failed to delete chat: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func (o *ChatHandler) ListOperatorChats(w http.ResponseWriter, r *http.Request) {
	chats, err := o.ChatService.ListOperatorChats(r.Context())
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to list chats: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"chats": chats})
}

func (o *ChatHandler) GetOperatorChat(w http.ResponseWriter, r *http.Request) {
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

	detail, err := o.ChatService.GetOperatorChat(r.Context(), chatID)
	if err != nil {
		if errors.Is(err, service.ErrChatNotFound) {
			http.Error(w, "chat not found", http.StatusNotFound)
			return
		}
		http.Error(w, fmt.Sprintf("failed to get chat detail: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(detail)
}

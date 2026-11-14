package service

import (
	"context"
	"github.com/google/uuid"
	"fmt"
)

type ChatRepository interface {
	CreateChat(ctx context.Context, sessionID uuid.UUID, chatID uuid.UUID) (uuid.UUID, error)
	GetChatHistory(ctx context.Context, chatID uuid.UUID, limit int) ([]HistoryUnit, error)
	GetChatSummary(ctx context.Context, chatID uuid.UUID) (string, error)
	UpdateChatSummary(ctx context.Context, chatID uuid.UUID, summary string) error
}

type RagRequest struct {
	Msg    string    
	History History 
	Summary string 
}

type AuthorType string
const (
	AuthorUser    AuthorType = "user"
	AuthorAssistant AuthorType = "assistant"
)

type History struct {
	units []HistoryUnit
}
type HistoryUnit struct {
	Author  AuthorType
	Message string 
}

type RagResponse struct {
	ID      string  
	Response string 
	ReadyForLead bool
	Sources sources  
}

type sources struct {
	DocID string 
	ChunkID string 
	FilePath string 
	Score int64 
	Text string 
}

type RagIntegration interface {
	Completions(ctx context.Context, req *RagRequest) (*RagResponse, error)
	GetSummary(ctx context.Context, chatID uuid.UUID) (string, error)
}


type Chat struct {
	chatRepo ChatRepository
	ragIntegration RagIntegration
}

func NewChatService(chatRepo ChatRepository) *Chat {
	return &Chat{chatRepo: chatRepo}
}

func (c *Chat) CreateChat(ctx context.Context, sessionID uuid.UUID) (uuid.UUID, error) {
	chatID := uuid.New()

	return c.chatRepo.CreateChat(ctx, sessionID, chatID)
}

func (c *Chat) ProcessIncomingMessage(ctx context.Context, query string, chatID uuid.UUID) (string, error) {
	chatHistory, err := c.chatRepo.GetChatHistory(ctx, chatID, 12)
	if err != nil {
		return "", fmt.Errorf("failed to get chat history: %w", err)
	}
	summary, err := c.chatRepo.GetChatSummary(ctx, chatID)
	if err != nil {
		return "", fmt.Errorf("failed to get chat summary: %w", err)
	}

	req := &RagRequest{
		Msg: query,
		History: History{
			units: chatHistory,
		},
		Summary: summary,
	}
	resp, err := c.ragIntegration.Completions(ctx, req)
	if err != nil {
		return "", fmt.Errorf("failed to get completion: %w", err)
	}

	go func() {
		summary, _ := c.ragIntegration.GetSummary(ctx, chatID)
		c.chatRepo.UpdateChatSummary(ctx, chatID, summary)
	}()

	return resp.Response, nil
}


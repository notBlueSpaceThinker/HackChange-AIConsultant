package service

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/google/uuid"
	"errors"
)

type ChatRepository interface {
	CreateChat(ctx context.Context, sessionID uuid.UUID, chatID uuid.UUID) (uuid.UUID, error)
	GetChatHistory(ctx context.Context, chatID uuid.UUID, limit int) ([]HistoryUnit, error)
	GetChatSummary(ctx context.Context, chatID uuid.UUID) (string, error)
	UpdateChatSummary(ctx context.Context, chatID uuid.UUID, summary string) error
}

type MessageRepository interface {
	SaveMessage(ctx context.Context, messageID uuid.UUID, chatID uuid.UUID, message string, author AuthorType) error
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
	Sources Sources  
}

type Sources struct {
	DocID string 
	ChunkID string 
	FilePath string 
	Score int64 
	Text string 
}

type RagIntegration interface {
	Completions(ctx context.Context, req *RagRequest) (*RagResponse, error)
	GetSummary(ctx context.Context, userMessage string, assistantMessage string, chatID uuid.UUID) (string, error)
}


type Chat struct {
	chatRepo ChatRepository
	ragIntegration RagIntegration
	messageRepo MessageRepository
}

func NewChatService(chatRepo ChatRepository, ragIntegration RagIntegration, messageRepo MessageRepository) *Chat {
	return &Chat{chatRepo: chatRepo, ragIntegration: ragIntegration, messageRepo: messageRepo}
}

func (c *Chat) CreateChat(ctx context.Context, sessionID uuid.UUID) (uuid.UUID, error) {
	chatID := uuid.New()

	return c.chatRepo.CreateChat(ctx, sessionID, chatID)
}

func (c *Chat) ProcessIncomingMessage(ctx context.Context, query string, chatID uuid.UUID) (string, error) {
	c.messageRepo.SaveMessage(ctx, uuid.New(), chatID, query, AuthorUser)
	
	chatHistory, err := c.chatRepo.GetChatHistory(ctx, chatID, 12)
	if err != nil && !errors.Is(err, sql.ErrNoRows){
		return "", fmt.Errorf("failed to get chat history: %w", err)
	}
	summary, err := c.chatRepo.GetChatSummary(ctx, chatID)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
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

	c.messageRepo.SaveMessage(ctx, uuid.New(), chatID, req.Msg, AuthorAssistant)

	go func() {
		summary, _ := c.ragIntegration.GetSummary(ctx, query, resp.Response, chatID)
		c.chatRepo.UpdateChatSummary(ctx, chatID, summary)
	}()

	return resp.Response, nil
}

func (c *Chat) GetChatHistory(ctx context.Context, chatID uuid.UUID) ([]string, error) {
	historyUnits, err := c.chatRepo.GetChatHistory(ctx, chatID, 100)
	if err != nil {
		return nil, fmt.Errorf("failed to get chat history: %w", err)
	}
	
	var history []string
	for _, unit := range historyUnits {
		history = append(history, fmt.Sprintf("%s: %s", unit.Author, unit.Message))
	}
	return history, nil
}
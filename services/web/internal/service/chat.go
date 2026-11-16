package service

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
)

var ErrChatNotFound = errors.New("chat not found")

type OperatorLead struct {
	FullName  string `json:"full_name"`
	Phone     string `json:"phone"`
	Company   string `json:"company"`
	CreatedAt string `json:"created_at,omitempty"`
}

type OperatorChatSummary struct {
	ChatID        string        `json:"chat_id"`
	SessionID     string        `json:"session_id"`
	Title         string        `json:"title"`
	Status        string        `json:"status"`
	HasLead       bool          `json:"has_lead"`
	Summary       string        `json:"summary"`
	MessageCount  int           `json:"message_count"`
	CreatedAt     string        `json:"created_at,omitempty"`
	LastMessageAt string        `json:"last_message_at,omitempty"`
	Lead          *OperatorLead `json:"lead,omitempty"`
}

type OperatorProfiler struct {
	EmbeddingTime  *float64 `json:"embedding_time,omitempty"`
	DBSearchTime   *float64 `json:"db_search_time,omitempty"`
	RerankingTime  *float64 `json:"reranking_time,omitempty"`
	GenerationTime *float64 `json:"generation_time,omitempty"`
	RagTime        *float64 `json:"rag_time,omitempty"`
	SummarizerTime *float64 `json:"summarizer_time,omitempty"`
}

type OperatorChatStats struct {
	AssistantMessages int      `json:"assistant_messages"`
	ProfiledMessages  int      `json:"profiled_messages"`
	AvgEmbeddingTime  *float64 `json:"avg_embedding_time"`
	AvgDBSearchTime   *float64 `json:"avg_db_search_time"`
	AvgRerankingTime  *float64 `json:"avg_reranking_time"`
	AvgGenerationTime *float64 `json:"avg_generation_time"`
	AvgRagTime        *float64 `json:"avg_rag_time"`
	AvgSummarizerTime *float64 `json:"avg_summarizer_time,omitempty"`
}

type OperatorMessage struct {
	ID        string            `json:"id"`
	Author    string            `json:"author"`
	Message   string            `json:"message"`
	CreatedAt string            `json:"created_at,omitempty"`
	Sources   []Sources         `json:"sources,omitempty"`
	Profiler  *OperatorProfiler `json:"profiler,omitempty"`
}

type OperatorChatDetail struct {
	ChatID    string            `json:"chat_id"`
	SessionID string            `json:"session_id"`
	Status    string            `json:"status"`
	HasLead   bool              `json:"has_lead"`
	Summary   string            `json:"summary"`
	CreatedAt string            `json:"created_at,omitempty"`
	Lead      *OperatorLead     `json:"lead,omitempty"`
	Stats     OperatorChatStats `json:"stats"`
	Messages  []OperatorMessage `json:"messages"`
}

type ChatRepository interface {
	CreateChat(ctx context.Context, sessionID uuid.UUID, chatID uuid.UUID) (uuid.UUID, error)
	GetChatHistory(ctx context.Context, chatID uuid.UUID, limit int) ([]HistoryUnit, error)
	GetChatSummary(ctx context.Context, chatID uuid.UUID) (string, error)
	UpdateChatSummary(ctx context.Context, chatID uuid.UUID, resp string) error
	DeleteChat(ctx context.Context, chatID uuid.UUID) error
	ListOperatorChats(ctx context.Context) ([]OperatorChatSummary, error)
	GetOperatorChat(ctx context.Context, chatID uuid.UUID) (*OperatorChatDetail, error)
}

type MessageRepository interface {
	SaveMessage(ctx context.Context, messageID uuid.UUID, chatID uuid.UUID, message string, author AuthorType, sources []Sources, profiler *RagProfiler) error
	UpdateMessageSummarizerTime(ctx context.Context, messageID uuid.UUID, summarizerTime float64) error
}

type RagRequest struct {
	SessionID string
	Msg       string
	History   []HistoryUnit
	Summary   string
}

type AuthorType string

const (
	AuthorUser      AuthorType = "user"
	AuthorAssistant AuthorType = "assistant"
)

type HistoryUnit struct {
	Author  AuthorType
	Message string
}

type RagResponse struct {
	SessionID    string
	Response     string
	ReadyForLead bool
	Sources      []Sources
	Profiler     RagProfiler
}

type RagProfiler struct {
	EmbeddingTime  *float64 `json:"embedding_time"`
	DBSearchTime   *float64 `json:"db_search_time"`
	RerankingTime  *float64 `json:"reranking_time"`
	GenerationTime *float64 `json:"generation_time"`
	RagTime        *float64 `json:"rag_time"`
}

type Sources struct {
	DocID    string  `json:"doc_id"`
	ChunkID  string  `json:"chunk_id"`
	FilePath string  `json:"filepath"`
	Title    string  `json:"title"`
	Score    float64 `json:"score"`
	Text     string  `json:"text"`
}

type DocumentChunk struct {
	ChunkID    string
	ChunkIndex int
	Title      string
	Text       string
}

type DocumentResp struct {
	DocID    string
	FilePath string
	Chunks   []DocumentChunk
}

type RagIntegration interface {
	Completions(ctx context.Context, req *RagRequest) (*RagResponse, error)
	GetSummary(ctx context.Context, userMessage string, assistantMessage string, chatID uuid.UUID, previousSummary string) (SummaryResp, error)
	GetDocument(ctx context.Context, docID string) (*DocumentResp, error)
}

type SummaryResp struct {
	Summary string
	SummarizerTime *float64
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

func (c *Chat) ProcessIncomingMessage(ctx context.Context, query string, chatID uuid.UUID) (*RagResponse, error) {
	chatHistory, err := c.chatRepo.GetChatHistory(ctx, chatID, 12)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, fmt.Errorf("failed to get chat history: %w", err)
	}
	summary, err := c.chatRepo.GetChatSummary(ctx, chatID)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, fmt.Errorf("failed to get chat summary: %w", err)
	}

	if err := c.messageRepo.SaveMessage(ctx, uuid.New(), chatID, query, AuthorUser, nil, nil); err != nil {
		return nil, fmt.Errorf("failed to save user message: %w", err)
	}

	req := &RagRequest{
		SessionID: chatID.String(),
		Msg:       query,
		History:   chatHistory,
		Summary:   summary,
	}
	resp, err := c.ragIntegration.Completions(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to get completion: %w", err)
	}

	assistantMsgID := uuid.New()
	if err := c.messageRepo.SaveMessage(ctx, assistantMsgID, chatID, resp.Response, AuthorAssistant, resp.Sources, &resp.Profiler); err != nil {
		log.Printf("failed to save assistant message: %v", err)
	}

	go func(msgID uuid.UUID, assistantReply, prevSummary string) {
		sumCtx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		defer cancel()
		sumResp, err := c.ragIntegration.GetSummary(sumCtx, query, assistantReply, chatID, prevSummary)
		if err != nil {
			log.Printf("failed to summarize chat %s: %v", chatID, err)
			return
		}
		if sumResp.Summary != "" {
			if err := c.chatRepo.UpdateChatSummary(sumCtx, chatID, sumResp.Summary); err != nil {
				log.Printf("failed to update chat summary %s: %v", chatID, err)
			}
		}
		if sumResp.SummarizerTime != nil {
			if err := c.messageRepo.UpdateMessageSummarizerTime(sumCtx, msgID, *sumResp.SummarizerTime); err != nil {
				log.Printf("failed to save summarizer timing %s: %v", msgID, err)
			}
		}
	}(assistantMsgID, resp.Response, summary)

	return resp, nil
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

func (c *Chat) GetDocument(ctx context.Context, docID string) (*DocumentResp, error) {
	return c.ragIntegration.GetDocument(ctx, docID)
}

func (c *Chat) DeleteChat(ctx context.Context, chatID uuid.UUID) error {
	return c.chatRepo.DeleteChat(ctx, chatID)
}

func (c *Chat) ListOperatorChats(ctx context.Context) ([]OperatorChatSummary, error) {
	return c.chatRepo.ListOperatorChats(ctx)
}

func (c *Chat) GetOperatorChat(ctx context.Context, chatID uuid.UUID) (*OperatorChatDetail, error) {
	return c.chatRepo.GetOperatorChat(ctx, chatID)
}
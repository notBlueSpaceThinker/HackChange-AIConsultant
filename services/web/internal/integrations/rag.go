package integrations

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"

	"github.com/google/uuid"
	"web/internal/service"
)

var ErrDocumentNotFound = errors.New("document not found")


type RagRequest struct {
	SessionID string    `json:"session_id"`
	Msg       string    `json:"msg"`
	History   []History `json:"history"`
	Summary   *string   `json:"summary,omitempty"`
}

type AuthorType string

const (
	AuthorUser      AuthorType = "user"
	AuthorAssistant AuthorType = "assistant"
)

type History struct {
	Author  AuthorType `json:"author"`
	Message string     `json:"message"`
}

type RagProfiler struct {
	EmbeddingTime  *float64 `json:"embedding_time,omitempty"`
	DBSearchTime   *float64 `json:"db_search_time,omitempty"`
	RerankingTime  *float64 `json:"reranking_time,omitempty"`
	GenerationTime *float64 `json:"generation_time,omitempty"`
	RagTime        *float64 `json:"rag_time,omitempty"`
}

type RagResponse struct {
	SessionID    string      `json:"session_id"`
	Response     string      `json:"response"`
	ReadyForLead bool        `json:"ready_for_lead"`
	Sources      []sources   `json:"sources"`
	Profiler     RagProfiler `json:"profiler"`
}

type sources struct {
	DocID    string  `json:"doc_id"`
	ChunkID  string  `json:"chunk_id"`
	FilePath string  `json:"filepath"`
	Title    string  `json:"title"`
	Score    float64 `json:"score"`
	Text     string  `json:"text"`
}

// ValidationErrorDetail описывает детали ошибки валидации (422)
type ValidationErrorDetail struct {
	Loc  []any  `json:"loc"`
	Msg  string `json:"msg"`
	Type string `json:"type"`
}

// HTTPValidationError возвращается при коде ответа 422
type HTTPValidationError struct {
	Detail []ValidationErrorDetail `json:"detail"`
}

type Rag struct {
	BaseURL    string
	HTTPClient *http.Client
}

func NewRag(baseURL string, client *http.Client) *Rag {
	if client == nil {
		client = http.DefaultClient
	}
	return &Rag{
		BaseURL:    baseURL,
		HTTPClient: client,
	}
}

// Completions отправляет запрос к эндпоинту /completions
func (r *Rag) Completions(ctx context.Context, req *service.RagRequest) (*service.RagResponse, error) {
	url := fmt.Sprintf("%s/completions", r.BaseURL)

	history := make([]History, 0, len(req.History))
	for _, h := range req.History {
		history = append(history, History{
			Author:  AuthorType(h.Author),
			Message: h.Message,
		})
	}
	var summary *string
	if req.Summary != "" {
		s := req.Summary
		summary = &s
	}

	payload := RagRequest{
		SessionID: req.SessionID,
		Msg:       req.Msg,
		History:   history,
		Summary:   summary,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create http request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := r.HTTPClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request execution failed: %w", err)
	}
	defer resp.Body.Close()

	switch resp.StatusCode {
	case http.StatusOK:
		var ragResp RagResponse
		if err := json.NewDecoder(resp.Body).Decode(&ragResp); err != nil {
			return nil, fmt.Errorf("failed to decode 200 response: %w", err)
		}
		mappedSources := make([]service.Sources, 0, len(ragResp.Sources))
		for _, s := range ragResp.Sources {
			mappedSources = append(mappedSources, service.Sources{
				DocID:    s.DocID,
				ChunkID:  s.ChunkID,
				FilePath: s.FilePath,
				Title:    s.Title,
				Score:    s.Score,
				Text:     s.Text,
			})
		}
		return &service.RagResponse{
			SessionID:    ragResp.SessionID,
			Response:     ragResp.Response,
			ReadyForLead: ragResp.ReadyForLead,
			Sources:      mappedSources,
			Profiler: service.RagProfiler{
				EmbeddingTime:  ragResp.Profiler.EmbeddingTime,
				DBSearchTime:   ragResp.Profiler.DBSearchTime,
				RerankingTime:  ragResp.Profiler.RerankingTime,
				GenerationTime: ragResp.Profiler.GenerationTime,
				RagTime:        ragResp.Profiler.RagTime,
			},
		}, nil

	case http.StatusUnprocessableEntity:
		var valErr HTTPValidationError
		if err := json.NewDecoder(resp.Body).Decode(&valErr); err == nil {
			return nil, fmt.Errorf("validation error (422): %v", valErr.Detail)
		}
		return nil, fmt.Errorf("validation error (422) occurred, but body could not be parsed")

	default:
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}
}

func (r *Rag) GetSummary(ctx context.Context, userMessage string, assistantMessage string, chatID uuid.UUID, previousSummary string) (service.SummaryResp, error) {
	url := fmt.Sprintf("%s/summarize", r.BaseURL)
	payload := map[string]any{
		"session_id":        chatID.String(),
		"user_message":      userMessage,
		"assistant_message": assistantMessage,
	}
	if previousSummary != "" {
		payload["summary"] = previousSummary
	}
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return service.SummaryResp{}, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(jsonData))
	if err != nil {
		return service.SummaryResp{}, fmt.Errorf("failed to create http request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := r.HTTPClient.Do(httpReq)
	if err != nil {
		return service.SummaryResp{}, fmt.Errorf("request execution failed: %w", err)
	}

	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return service.SummaryResp{}, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var summaryResp struct {
		Summary  string   `json:"summary"`
		Profiler Profiler `json:"profiler"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&summaryResp); err != nil {
		return service.SummaryResp{}, fmt.Errorf("failed to decode response: %w", err)
	}

	return service.SummaryResp{
		Summary:        summaryResp.Summary,
		SummarizerTime: summaryResp.Profiler.SummarizerTime,
	}, nil
}

type Profiler struct {
	SummarizerTime *float64 `json:"summarizer_time"`
}

func (r *Rag) GetDocument(ctx context.Context, docID string) (*service.DocumentResp, error) {
	reqURL := fmt.Sprintf("%s/documents/%s", r.BaseURL, url.PathEscape(docID))
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create http request: %w", err)
	}

	resp, err := r.HTTPClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request execution failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, ErrDocumentNotFound
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var docResp struct {
		DocID    string `json:"doc_id"`
		FilePath string `json:"filepath"`
		Chunks   []struct {
			ChunkID    string `json:"chunk_id"`
			ChunkIndex int    `json:"chunk_index"`
			Title      string `json:"title"`
			Text       string `json:"text"`
		} `json:"chunks"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&docResp); err != nil {
		return nil, fmt.Errorf("failed to decode document response: %w", err)
	}

	chunks := make([]service.DocumentChunk, 0, len(docResp.Chunks))
	for _, c := range docResp.Chunks {
		chunks = append(chunks, service.DocumentChunk{
			ChunkID:    c.ChunkID,
			ChunkIndex: c.ChunkIndex,
			Title:      c.Title,
			Text:       c.Text,
		})
	}
	return &service.DocumentResp{
		DocID:    docResp.DocID,
		FilePath: docResp.FilePath,
		Chunks:   chunks,
	}, nil
}
package integrations

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"github.com/google/uuid"
	"web/internal/service"
)


type RagRequest struct {
	Msg    string    `json:"msg"`
	History History `json:"history"`
	Summary string `json:"summary"`
}

type AuthorType string
const (
	AuthorUser    AuthorType = "user"
	AuthorAssistant AuthorType = "assistant"
)

type History struct {
	Author  AuthorType `json:"author"`
	Message string `json:"message"`
}

type RagProfiler struct {
	EmbeddingTime  *float64 `json:"embedding_time,omitempty"`
	DBSearchTime   *float64 `json:"db_search_time,omitempty"`
	RerankingTime  *float64 `json:"reranking_time,omitempty"`
	GenerationTime *float64 `json:"generation_time,omitempty"`
	RagTime        *float64 `json:"rag_time,omitempty"`
}

type RagResponse struct {
	ID           string      `json:"id"`
	Response     string      `json:"response"`
	ReadyForLead bool        `json:"ready_for_lead"`
	Sources      sources     `json:"sources"`
	Profiler     RagProfiler `json:"profiler"` // Метрики сгруппированы вместе
}

type sources struct {
	DocID string `json:"doc_id"`
	ChunkID string `json:"chunk_id"`
	FilePath string `json:"file_path"`
	Score int64 `json:"score"`
	Text string `json:"text"`
}

// ValidationErrorDetail описывает детали ошибки валидации (422)
type ValidationErrorDetail struct {
	Loc  []string `json:"loc"`
	Msg  string   `json:"msg"`
	Type string   `json:"type"`
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

	jsonData, err := json.Marshal(req)
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
		return &service.RagResponse{
			ID: ragResp.ID,
			Response: ragResp.Response,
			ReadyForLead: ragResp.ReadyForLead,
			Sources: service.Sources{
				DocID: ragResp.Sources.DocID,
				ChunkID: ragResp.Sources.ChunkID,
				FilePath: ragResp.Sources.FilePath,
				Score: ragResp.Sources.Score,
				Text: ragResp.Sources.Text,
			},
			Profiler: service.RagProfiler{
				EmbeddingTime : ragResp.Profiler.DBSearchTime,
				DBSearchTime: ragResp.Profiler.DBSearchTime,
				RerankingTime: ragResp.Profiler.RerankingTime,
				GenerationTime: ragResp.Profiler.GenerationTime,
				RagTime:ragResp.Profiler.RagTime,
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

func (r *Rag) GetSummary(ctx context.Context, userMessage string, assistantMessage string, chatID uuid.UUID) (service.SummaryResp, error) {
	// return "This is a mock summary from the GetSummary method.", nil
	
	url := fmt.Sprintf("%s/summary", r.BaseURL)
	jsonData, err := json.Marshal(map[string]interface{}{
		"user_message":      userMessage,
		"assistant_message": assistantMessage,
		"chat_id":           chatID.String(),
	})

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
		Summary string `json:"summary"`
		Profiler Profiler `json:"profiler"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&summaryResp); err != nil {
		return service.SummaryResp{}, fmt.Errorf("failed to decode response: %w", err)
	}

	return service.SummaryResp{

	}, nil
}

type Profiler struct {
	SummarizerTime *float64 `json:"summarizer_time"`
} 
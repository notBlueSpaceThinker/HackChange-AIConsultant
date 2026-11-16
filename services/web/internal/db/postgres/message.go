package postgres

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"web/internal/service"
)

type MessageRepository struct {
	pool *pgxpool.Pool
}

func NewMessageRepository(pool *pgxpool.Pool) *MessageRepository {
	return &MessageRepository{pool: pool}
}

func (r *MessageRepository) SaveMessage(
	ctx context.Context,
	messageID uuid.UUID,
	chatID uuid.UUID,
	message string,
	author service.AuthorType,
	sources []service.Sources,
	profiler *service.RagProfiler,
) error {
	var sourcesJSON []byte
	if sources != nil {
		var err error
		sourcesJSON, err = json.Marshal(sources)
		if err != nil {
			return fmt.Errorf("ошибка сериализации источников: %w", err)
		}
	}

	var profilerJSON []byte
	if profiler != nil {
		var err error
		profilerJSON, err = json.Marshal(profiler)
		if err != nil {
			return fmt.Errorf("ошибка сериализации профайлера: %w", err)
		}
	}

	query := "INSERT INTO message (id, chat_id, message, author, sources, profiler) VALUES ($1, $2, $3, $4, $5, $6)"
	_, err := r.pool.Exec(ctx, query, messageID, chatID, message, author, sourcesJSON, profilerJSON)
	if err != nil {
		return fmt.Errorf("ошибка сохранения сообщения: %w", err)
	}
	return nil
}

func (r *MessageRepository) UpdateMessageSummarizerTime(
	ctx context.Context,
	messageID uuid.UUID,
	summarizerTime float64,
) error {
	query := `
		UPDATE message
		SET profiler = COALESCE(profiler, '{}'::jsonb) || jsonb_build_object('summarizer_time', $1::double precision)
		WHERE id = $2
	`
	if _, err := r.pool.Exec(ctx, query, summarizerTime, messageID); err != nil {
		return fmt.Errorf("ошибка обновления времени суммаризации: %w", err)
	}
	return nil
}

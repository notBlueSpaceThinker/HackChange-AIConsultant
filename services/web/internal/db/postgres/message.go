package postgres

import (
	"context"
	"fmt"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/google/uuid"
	"web/internal/service"
)

type MessageRepository struct {
	pool *pgxpool.Pool
}

func NewMessageRepository(pool *pgxpool.Pool) *MessageRepository {
	return &MessageRepository{pool: pool}
}

func (r *MessageRepository) SaveMessage(ctx context.Context, messageID uuid.UUID, chatID uuid.UUID, message string, author service.AuthorType) error {
	query := "INSERT INTO message (id, chat_id, message, author) VALUES ($1, $2, $3, $4)"
	_, err := r.pool.Exec(ctx, query, messageID, chatID, message, author)
	if err != nil {
		return fmt.Errorf("ошибка сохранения сообщения: %w", err)
	}
	return nil
}

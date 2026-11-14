package postgres

import (
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/google/uuid"
	sq "github.com/Masterminds/squirrel"
	"context"
)

type ChatRepository struct {
	pool *pgxpool.Pool
}

func NewChatRepository(pool *pgxpool.Pool) *ChatRepository {
	return &ChatRepository{pool: pool}
}

func CreateChat(ctx context.Context) (uuid.UUID, error) {
	chatID := uuid.New()

	query, args, err := sq.Insert("chats").
		Columns("id"). 
		Values(chatID).
		PlaceholderFormat(sq.Dollar). 
		ToSql()
	if err != nil {
		return uuid.Nil, fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	// 3. Выполняем запрос через пул соединений pgxpool
	_, err = pool.Exec(ctx, query, args...)
	if err != nil {
		return uuid.Nil, fmt.Errorf("ошибка создания чата: %w", err)
	}

	return chatID, nil
}
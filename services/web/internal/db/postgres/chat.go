package postgres

import (
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/google/uuid"
	sq "github.com/Masterminds/squirrel"
	"context"
	"fmt"
	service "web/internal/service"
)

type ChatRepository struct {
	pool *pgxpool.Pool
}

func NewChatRepository(pool *pgxpool.Pool) *ChatRepository {
	return &ChatRepository{pool: pool}
}

func (r *ChatRepository) CreateChat(ctx context.Context, session_id uuid.UUID, chatID uuid.UUID) (uuid.UUID, error) {
	query, args, err := sq.Insert("chat").
		Columns("id", "session_id").
		Values(chatID, session_id).
		PlaceholderFormat(sq.Dollar). 
		ToSql()
	if err != nil {
		return uuid.Nil, fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	_, err = r.pool.Exec(ctx, query, args...)
	if err != nil {
		return uuid.Nil, fmt.Errorf("ошибка создания чата: %w", err)
	}

	return chatID, nil
}

func (r *ChatRepository) GetChatHistory(ctx context.Context, chatID uuid.UUID, limit int) ([]service.HistoryUnit, error) {
	query, args, err := sq.Select("author", "message").
		From("chat_history").
		Where(sq.Eq{"chat_id": chatID}).
		OrderBy("created_at DESC").
		Limit(uint64(limit)).
		PlaceholderFormat(sq.Dollar).
		ToSql()
	if err != nil {
		return nil, fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}
	defer rows.Close()

	var history []service.HistoryUnit
	for rows.Next() {
		var unit service.HistoryUnit
		if err := rows.Scan(&unit.Author, &unit.Message); err != nil {
			return nil, fmt.Errorf("ошибка сканирования строки: %w", err)
		}
		history = append(history, unit)
	}
	return history, nil
}

func (r *ChatRepository) GetChatSummary(ctx context.Context, chatID uuid.UUID) (string, error) {
	query, args, err := sq.Select("summary").
		From("chat").
		Where(sq.Eq{"id": chatID}).
		PlaceholderFormat(sq.Dollar).
		ToSql()
	if err != nil {
		return "", fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	row := r.pool.QueryRow(ctx, query, args...)
	var summary string
	if err := row.Scan(&summary); err != nil {
		return "", fmt.Errorf("ошибка сканирования строки: %w", err)
	}
	return summary, nil
}


func (r *ChatRepository) UpdateChatSummary(ctx context.Context, chatID uuid.UUID, summary string) error {
	query, args, err := sq.Update("chat").
		Set("summary", summary).
		Where(sq.Eq{"id": chatID}).
		PlaceholderFormat(sq.Dollar).
		ToSql()
	if err != nil {
		return fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	_, err = r.pool.Exec(ctx, query, args...)
	if err != nil {
		return fmt.Errorf("ошибка обновления сводки чата: %w", err)
	}

	return nil
}
package postgres

import (
	"context"
	"fmt"

	sq "github.com/Masterminds/squirrel"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

type ProfileRepository struct {
	pool *pgxpool.Pool
}

func NewProfileRepository(pool *pgxpool.Pool) *ProfileRepository {
	return &ProfileRepository{pool: pool}
}

func (r *ProfileRepository) CreateProfile(ctx context.Context, userID uuid.UUID, sessionID, chatID, fullName, phone, company string) error {
	sessionUUID, err := uuid.Parse(sessionID)
	if err != nil {
		return fmt.Errorf("некорректный session_id: %w", err)
	}

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("ошибка начала транзакции: %w", err)
	}
	defer tx.Rollback(ctx)

	var chatUUIDPtr *uuid.UUID
	if chatID != "" {
		parsedChatID, err := uuid.Parse(chatID)
		if err != nil {
			return fmt.Errorf("некорректный chat_id: %w", err)
		}
		chatUUIDPtr = &parsedChatID
	}

	query, args, err := sq.Insert("profile").
		Columns("id", "session_id", "chat_id", "full_name", "phone", "company").
		Values(userID, sessionUUID, chatUUIDPtr, fullName, phone, company).
		PlaceholderFormat(sq.Dollar).
		ToSql()
	if err != nil {
		return fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	if _, err = tx.Exec(ctx, query, args...); err != nil {
		return fmt.Errorf("ошибка создания профиля: %w", err)
	}

	if chatUUIDPtr != nil {
		if _, err = tx.Exec(ctx, "UPDATE chat SET user_id = $1 WHERE id = $2", userID, *chatUUIDPtr); err != nil {
			return fmt.Errorf("ошибка привязки профиля к чату: %w", err)
		}
	} else {
		_, err = tx.Exec(
			ctx,
			"UPDATE chat SET user_id = $1 WHERE id = (SELECT id FROM chat WHERE session_id = $2 ORDER BY created_at DESC LIMIT 1)",
			userID,
			sessionUUID,
		)
		if err != nil {
			return fmt.Errorf("ошибка привязки профиля к последнему чату сессии: %w", err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("ошибка фиксации транзакции: %w", err)
	}

	return nil
}
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

func (r *ProfileRepository) CreateProfile(ctx context.Context, userID uuid.UUID, sessionID, fullName, phone, company string) error {
	query, args, err := sq.Insert("profile").
		Columns("id",  "full_name", "phone", "company").
		Values(userID, fullName, phone, company).
		PlaceholderFormat(sq.Dollar). 
		ToSql()
	if err != nil {
		return fmt.Errorf("ошибка сборки SQL: %w", err)
	}

	_, err = r.pool.Exec(ctx, query, args...)
	if err != nil {
		return fmt.Errorf("ошибка создания профиля: %w", err)
	}

	return nil
}
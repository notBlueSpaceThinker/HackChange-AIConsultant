package postgres

import(
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/google/uuid"
	sq "github.com/Masterminds/squirrel"
	"context"
	"fmt"
)

type UserRepository struct {
	pool *pgxpool.Pool
}

func NewUserRepository(pool *pgxpool.Pool) *UserRepository {
	return &UserRepository{pool: pool}
}

func (r *UserRepository) CreateProfile(ctx context.Context, userID uuid.UUID, sessionID, fullName, phone, company string) error {
	query, args, err := sq.Insert("user").
		Columns("id", "session_id", "full_name", "phone", "company").
		Values(userID, sessionID, fullName, phone, company).
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
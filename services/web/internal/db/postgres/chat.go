package postgres

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	sq "github.com/Masterminds/squirrel"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
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
	query, args, err := sq.Select("message.author", "message.message").
		From("chat").
		Join("message ON chat.id = message.chat_id").
		Where(sq.Eq{"chat.id": chatID}).
		OrderBy("message.created_at DESC").
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
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("ошибка чтения строк истории: %w", err)
	}
	for i, j := 0, len(history)-1; i < j; i, j = i+1, j-1 {
		history[i], history[j] = history[j], history[i]
	}
	return history, nil
}

func (r *ChatRepository) GetChatSummary(ctx context.Context, chatID uuid.UUID) (string, error) {
	query, args, err := sq.Select("COALESCE(summary, '')").
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

func (r *ChatRepository) DeleteChat(ctx context.Context, chatID uuid.UUID) error {
	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("ошибка начала транзакции: %w", err)
	}
	defer tx.Rollback(ctx)

	if _, err := tx.Exec(ctx, "DELETE FROM message WHERE chat_id = $1", chatID); err != nil {
		return fmt.Errorf("ошибка удаления сообщений чата: %w", err)
	}
	if _, err := tx.Exec(ctx, "DELETE FROM chat WHERE id = $1", chatID); err != nil {
		return fmt.Errorf("ошибка удаления чата: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("ошибка фиксации транзакции: %w", err)
	}
	return nil
}

func (r *ChatRepository) ListOperatorChats(ctx context.Context) ([]service.OperatorChatSummary, error) {
	query := `
		SELECT
			c.id::text,
			c.session_id::text,
			COALESCE(c.summary, ''),
			COALESCE((
				SELECT m.message
				FROM message m
				WHERE m.chat_id = c.id AND m.author = 'user'
				ORDER BY m.created_at ASC
				LIMIT 1
			), 'Новый диалог') AS title,
			(SELECT COUNT(*) FROM message m WHERE m.chat_id = c.id) AS msg_count,
			c.created_at,
			COALESCE((SELECT MAX(m.created_at) FROM message m WHERE m.chat_id = c.id), c.created_at) AS last_activity,
			p.full_name,
			p.phone,
			p.company,
			p.created_at
		FROM chat c
		LEFT JOIN profile p ON p.id = c.user_id
		ORDER BY (p.id IS NOT NULL) DESC, last_activity DESC
	`
	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("ошибка получения списка чатов: %w", err)
	}
	defer rows.Close()

	chats := make([]service.OperatorChatSummary, 0)
	for rows.Next() {
		var (
			item         service.OperatorChatSummary
			createdAt    *time.Time
			lastActivity *time.Time
			fullName     *string
			phone        *string
			company      *string
			leadCreated  *time.Time
		)
		if err := rows.Scan(
			&item.ChatID,
			&item.SessionID,
			&item.Summary,
			&item.Title,
			&item.MessageCount,
			&createdAt,
			&lastActivity,
			&fullName,
			&phone,
			&company,
			&leadCreated,
		); err != nil {
			return nil, fmt.Errorf("ошибка сканирования чата: %w", err)
		}
		if createdAt != nil {
			item.CreatedAt = createdAt.UTC().Format(time.RFC3339)
		}
		if lastActivity != nil {
			item.LastMessageAt = lastActivity.UTC().Format(time.RFC3339)
		}
		if fullName != nil {
			item.HasLead = true
			item.Status = "closed"
			lead := &service.OperatorLead{
				FullName: *fullName,
			}
			if phone != nil {
				lead.Phone = *phone
			}
			if company != nil {
				lead.Company = *company
			}
			if leadCreated != nil {
				lead.CreatedAt = leadCreated.UTC().Format(time.RFC3339)
			}
			item.Lead = lead
		} else {
			item.Status = "open"
		}
		chats = append(chats, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("ошибка чтения списка чатов: %w", err)
	}
	return chats, nil
}

func (r *ChatRepository) GetOperatorChat(ctx context.Context, chatID uuid.UUID) (*service.OperatorChatDetail, error) {
	chatQuery := `
		SELECT
			c.id::text,
			c.session_id::text,
			COALESCE(c.summary, ''),
			c.created_at,
			p.full_name,
			p.phone,
			p.company,
			p.created_at
		FROM chat c
		LEFT JOIN profile p ON p.id = c.user_id
		WHERE c.id = $1
	`
	var (
		detail      service.OperatorChatDetail
		createdAt   *time.Time
		fullName    *string
		phone       *string
		company     *string
		leadCreated *time.Time
	)
	err := r.pool.QueryRow(ctx, chatQuery, chatID).Scan(
		&detail.ChatID,
		&detail.SessionID,
		&detail.Summary,
		&createdAt,
		&fullName,
		&phone,
		&company,
		&leadCreated,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, service.ErrChatNotFound
		}
		return nil, fmt.Errorf("ошибка получения чата: %w", err)
	}
	if createdAt != nil {
		detail.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	}
	if fullName != nil {
		detail.HasLead = true
		detail.Status = "closed"
		lead := &service.OperatorLead{FullName: *fullName}
		if phone != nil {
			lead.Phone = *phone
		}
		if company != nil {
			lead.Company = *company
		}
		if leadCreated != nil {
			lead.CreatedAt = leadCreated.UTC().Format(time.RFC3339)
		}
		detail.Lead = lead
	} else {
		detail.Status = "open"
	}

	msgRows, err := r.pool.Query(
		ctx,
		"SELECT id::text, author::text, message, created_at, sources, profiler FROM message WHERE chat_id = $1 ORDER BY created_at ASC",
		chatID,
	)
	if err != nil {
		return nil, fmt.Errorf("ошибка получения сообщений чата: %w", err)
	}
	defer msgRows.Close()

	detail.Messages = make([]service.OperatorMessage, 0)
	for msgRows.Next() {
		var (
			msg          service.OperatorMessage
			msgTime      *time.Time
			sourcesRaw   []byte
			profilerRaw  []byte
		)
		if err := msgRows.Scan(&msg.ID, &msg.Author, &msg.Message, &msgTime, &sourcesRaw, &profilerRaw); err != nil {
			return nil, fmt.Errorf("ошибка сканирования сообщения: %w", err)
		}
		if msgTime != nil {
			msg.CreatedAt = msgTime.UTC().Format(time.RFC3339)
		}
		if len(sourcesRaw) > 0 {
			var sources []service.Sources
			if err := json.Unmarshal(sourcesRaw, &sources); err == nil {
				msg.Sources = sources
			}
		}
		if len(profilerRaw) > 0 {
			var profiler service.OperatorProfiler
			if err := json.Unmarshal(profilerRaw, &profiler); err == nil {
				msg.Profiler = &profiler
			}
		}
		detail.Messages = append(detail.Messages, msg)
	}
	if err := msgRows.Err(); err != nil {
		return nil, fmt.Errorf("ошибка чтения сообщений чата: %w", err)
	}
	detail.Stats = computeOperatorStats(detail.Messages)
	return &detail, nil
}

type avgAccumulator struct {
	sum   float64
	count int
}

func (a *avgAccumulator) add(val *float64) {
	if val != nil {
		a.sum += *val
		a.count++
	}
}

func (a *avgAccumulator) mean() *float64 {
	if a.count == 0 {
		return nil
	}
	v := a.sum / float64(a.count)
	return &v
}

func computeOperatorStats(messages []service.OperatorMessage) service.OperatorChatStats {
	var (
		stats    service.OperatorChatStats
		embAcc   avgAccumulator
		dbAcc    avgAccumulator
		rrkAcc   avgAccumulator
		genAcc   avgAccumulator
		ragAcc   avgAccumulator
		sumAcc   avgAccumulator
	)
	for _, m := range messages {
		if m.Author == string(service.AuthorAssistant) {
			stats.AssistantMessages++
		}
		if m.Profiler == nil {
			continue
		}
		stats.ProfiledMessages++
		embAcc.add(m.Profiler.EmbeddingTime)
		dbAcc.add(m.Profiler.DBSearchTime)
		rrkAcc.add(m.Profiler.RerankingTime)
		genAcc.add(m.Profiler.GenerationTime)
		ragAcc.add(m.Profiler.RagTime)
		sumAcc.add(m.Profiler.SummarizerTime)
	}
	stats.AvgEmbeddingTime = embAcc.mean()
	stats.AvgDBSearchTime = dbAcc.mean()
	stats.AvgRerankingTime = rrkAcc.mean()
	stats.AvgGenerationTime = genAcc.mean()
	stats.AvgRagTime = ragAcc.mean()
	stats.AvgSummarizerTime = sumAcc.mean()
	return stats
}
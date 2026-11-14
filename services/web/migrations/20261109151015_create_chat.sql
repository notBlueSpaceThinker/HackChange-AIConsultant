-- +goose Up
CREATE TABLE IF NOT EXISTS chat (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    user_id UUID,
);

CREATE INDEX IF NOT EXISTS idx_chat_user_id ON chat(session_id);

-- +goose Down
SELECT 'down SQL query';

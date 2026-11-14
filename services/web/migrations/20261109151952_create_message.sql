-- +goose Up
SELECT 'up SQL query';

CREATE TABLE IF NOT EXISTS message (
    id uuid PRIMARY KEY,
    chat_id INT NOT NULL REFERENCES chat(id),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_message_chat_id ON message(chat_id);

-- +goose Down
SELECT 'down SQL query';

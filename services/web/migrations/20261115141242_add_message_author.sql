-- +goose Up

CREATE TYPE author_type AS ENUM (
    'user',
    'assistant'
);

ALTER TABLE message
ADD COLUMN author author_type NOT NULL;


-- +goose Down

ALTER TABLE message
DROP COLUMN author;

DROP TYPE author_type;
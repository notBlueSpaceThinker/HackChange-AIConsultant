-- +goose Up
SELECT 'up SQL query';
CREATE TABLE IF NOT EXISTS user (
    id uuid PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) ,
    company VARCHAR(255) ,
);



-- +goose Down
SELECT 'down SQL query';

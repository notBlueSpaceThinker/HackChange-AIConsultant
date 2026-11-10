FROM golang:1.26-alpine

WORKDIR /app

# Копируем зависимости из контекста (теперь это services/web)
COPY go.mod go.sum ./
RUN go mod download

# Копируем весь остальной код из папки services/web
COPY . .

# Собираем проект из локальной папки cmd, которая теперь находится в корне контекста
RUN go build -o main ./cmd/web

EXPOSE 8080

CMD ["./main"]

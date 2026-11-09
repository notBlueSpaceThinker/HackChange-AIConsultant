package web

import (
	"context"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
}
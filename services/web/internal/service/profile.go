package service

import (
	"context"

	"github.com/google/uuid"
)

type UserRepository interface {
	CreateProfile(ctx context.Context, userID uuid.UUID, sessionID, fullName, phone, company string) error
}

type User struct {
	userRepo UserRepository
}

func (u *User) CreateProfile(ctx context.Context, sessionID, fullName, phone, company string) error {
	userID := uuid.New()
	return u.userRepo.CreateProfile(ctx, userID, sessionID, fullName, phone, company)
}
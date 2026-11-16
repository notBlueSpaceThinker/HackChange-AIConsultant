package service

import (
	"context"

	"github.com/google/uuid"
)

type ProfileRepository interface {
	CreateProfile(ctx context.Context, userID uuid.UUID, sessionID, chatID, fullName, phone, company string) error
}

type Profile struct {
	profileRepo ProfileRepository
}

func NewProfileService(profileRepo ProfileRepository) *Profile {
	return &Profile{profileRepo: profileRepo}
}

func (p *Profile) CreateProfile(ctx context.Context, sessionID, chatID, fullName, phone, company string) error {
	userID := uuid.New()
	return p.profileRepo.CreateProfile(ctx, userID, sessionID, chatID, fullName, phone, company)
}
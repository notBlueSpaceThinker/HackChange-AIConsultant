package handler

type ProfileService interface {
	CreateProfile(sessionID string, fullName, phone, company string) error
}

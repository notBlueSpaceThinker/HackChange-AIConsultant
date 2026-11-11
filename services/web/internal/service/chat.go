package service

type Chat struct {
}

func NewChatService() *Chat {
	return &Chat{}
}


func (c *Chat) ProcessIncomingMessage(query string) (string, error) {
	//todo: реализовать логику получения сообщения
	return "response from LLM to query: " + query, nil
}

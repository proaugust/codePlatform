package model

type Book struct {
	ID     int    `json:"id"`
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

func (b *Book) Clone() *Book {
	if b == nil {
		return nil
	}
	c := *b
	return &c
}

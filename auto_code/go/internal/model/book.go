package model

import "time"

type Book struct {
	ID        int64     `json:"id"`
	Title     string    `json:"title"`
	Author    string    `json:"author"`
	Stock     int       `json:"stock"`
	CreatedAt time.Time `json:"created_at"`
}

func (b *Book) Clone() *Book {
	if b == nil {
		return nil
	}
	c := *b
	return &c
}

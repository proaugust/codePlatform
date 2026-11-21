package service

import (
	"errors"
	"strings"

	"example.com/autocode/internal/model"
	"example.com/autocode/internal/repository"
)

type BookService struct {
	repo *repository.BookRepository
}

func NewBookService(repo *repository.BookRepository) *BookService {
	return &BookService{repo: repo}
}

func (s *BookService) ListBooks() ([]*model.Book, error) {
	return s.repo.List(), nil
}

func (s *BookService) GetBook(id int) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidArgument("invalid book id")
	}
	b, err := s.repo.Get(id)
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func (s *BookService) CreateBook(title, author string, stock int) (*model.Book, error) {
	title = strings.TrimSpace(title)
	author = strings.TrimSpace(author)
	if title == "" || len(title) > 200 || author == "" || len(author) > 100 || stock < 0 {
		return nil, ErrInvalidArgument("invalid title, author or stock")
	}
	b, err := s.repo.Create(&model.Book{Title: title, Author: author, Stock: stock})
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func (s *BookService) DeleteBook(id int) error {
	if id <= 0 {
		return ErrInvalidArgument("invalid book id")
	}
	if err := s.repo.Delete(id); err != nil {
		return mapRepoErr(err)
	}
	return nil
}

func (s *BookService) UpdateStock(id, delta int) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidArgument("invalid book id")
	}
	b, err := s.repo.UpdateStock(id, delta)
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func mapRepoErr(err error) error {
	switch {
	case errors.Is(err, repository.ErrNotFound):
		return ErrNotFound("book not found")
	case errors.Is(err, repository.ErrInvalidArgument):
		return ErrInvalidArgument(err.Error())
	default:
		return err
	}
}

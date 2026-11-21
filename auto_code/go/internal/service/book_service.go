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

func (s *BookService) GetBook(id int64) (*model.Book, error) {
	if id <= 0 {
		return nil, NewInvalidArgument("图书 id 必须为大于 0 的整数")
	}
	b, err := s.repo.Get(id)
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func (s *BookService) CreateBook(title, author string, stock int) (*model.Book, error) {
	return s.CreateBookWithID(0, title, author, stock)
}

func (s *BookService) CreateBookWithID(id int64, title, author string, stock int) (*model.Book, error) {
	if id < 0 {
		return nil, NewInvalidArgument("图书 id 必须为大于 0 的整数")
	}
	title = strings.TrimSpace(title)
	author = strings.TrimSpace(author)
	if title == "" || len(title) > 200 || author == "" || len(author) > 100 || stock < 0 {
		return nil, NewInvalidArgument("invalid title, author or stock")
	}
	b, err := s.repo.Create(&model.Book{ID: id, Title: title, Author: author, Stock: stock})
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func (s *BookService) DeleteBook(id int64) error {
	if id <= 0 {
		return NewInvalidArgument("图书 id 必须为大于 0 的整数")
	}
	if err := s.repo.Delete(id); err != nil {
		return mapRepoErr(err)
	}
	return nil
}

func (s *BookService) UpdateStock(id int64, delta int) (*model.Book, error) {
	if id <= 0 {
		return nil, NewInvalidArgument("图书 id 必须为大于 0 的整数")
	}
	b, err := s.repo.UpdateStock(id, delta)
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func (s *BookService) SetStock(id int64, stock int) (*model.Book, error) {
	if id <= 0 {
		return nil, NewInvalidArgument("图书 id 必须为大于 0 的整数")
	}
	if stock < 0 {
		return nil, NewInvalidArgument("stock must be >= 0")
	}
	b, err := s.repo.SetStock(id, stock)
	if err != nil {
		return nil, mapRepoErr(err)
	}
	return b, nil
}

func mapRepoErr(err error) error {
	switch {
	case errors.Is(err, repository.ErrNotFound):
		return NewNotFound("图书不存在")
	case errors.Is(err, repository.ErrInvalidArgument):
		return NewInvalidArgument("%s", err.Error())
	default:
		return err
	}
}

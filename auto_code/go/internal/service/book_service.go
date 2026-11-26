package service

import (
	"context"
	"errors"
	"log"
	"strings"

	"example.com/autocode/internal/model"
	"example.com/autocode/internal/repository"

	"github.com/jackc/pgx/v5/pgconn"
)

type BookService struct {
	repo *repository.BookRepository
}

func NewBookService(repo *repository.BookRepository) *BookService {
	return &BookService{repo: repo}
}

func mapRepoError(err error) error {
	if err == nil {
		return nil
	}
	var ae *ApiError
	if errors.As(err, &ae) {
		return ae
	}
	if errors.Is(err, repository.ErrNotFound) {
		return ErrNotFound
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23514" {
		return ErrValidation
	}
	log.Printf("store error: %v", err)
	return ErrInternal
}

func validateBook(req model.BookRequest) (string, string, error) {
	title := strings.TrimSpace(req.Title)
	author := strings.TrimSpace(req.Author)
	if title == "" || req.Stock < 0 {
		return "", "", ErrValidation
	}
	return title, author, nil
}

func (s *BookService) List(ctx context.Context) ([]*model.Book, error) {
	books, err := s.repo.List(ctx)
	if err != nil {
		return nil, mapRepoError(err)
	}
	return books, nil
}

func (s *BookService) Get(ctx context.Context, id int64) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidID
	}
	book, err := s.repo.Get(ctx, id)
	if err != nil {
		return nil, mapRepoError(err)
	}
	return book, nil
}

func (s *BookService) Create(ctx context.Context, req model.BookRequest) (*model.Book, error) {
	title, author, err := validateBook(req)
	if err != nil {
		return nil, err
	}
	book, err := s.repo.Create(ctx, title, author, req.Stock)
	if err != nil {
		return nil, mapRepoError(err)
	}
	return book, nil
}

func (s *BookService) Update(ctx context.Context, id int64, req model.BookRequest) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidID
	}
	title, author, err := validateBook(req)
	if err != nil {
		return nil, err
	}
	book, err := s.repo.Update(ctx, id, title, author, req.Stock)
	if err != nil {
		return nil, mapRepoError(err)
	}
	return book, nil
}

func (s *BookService) SetStock(ctx context.Context, id int64, stock int) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidID
	}
	if stock < 0 {
		return nil, ErrValidation
	}
	book, err := s.repo.SetStock(ctx, id, stock)
	if err != nil {
		return nil, mapRepoError(err)
	}
	return book, nil
}

func (s *BookService) Delete(ctx context.Context, id int64) error {
	if id <= 0 {
		return ErrInvalidID
	}
	if err := s.repo.Delete(ctx, id); err != nil {
		return mapRepoError(err)
	}
	return nil
}

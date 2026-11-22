package repository

import (
	"errors"
	"sort"
	"sync"

	"example.com/autocode/internal/model"
)

var (
	ErrNotFound        = errors.New("book not found")
	ErrInvalidArgument = errors.New("invalid argument")
)

type BookRepository struct {
	mu     sync.RWMutex
	books  map[int64]*model.Book
	nextID int64
}

func NewBookRepository() *BookRepository {
	return &BookRepository{books: make(map[int64]*model.Book), nextID: 1}
}

func (r *BookRepository) List() []*model.Book {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]*model.Book, 0, len(r.books))
	for _, b := range r.books {
		cp := *b
		out = append(out, &cp)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

func (r *BookRepository) Get(id int64) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidArgument
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	b, ok := r.books[id]
	if !ok {
		return nil, ErrNotFound
	}
	cp := *b
	return &cp, nil
}

func (r *BookRepository) Create(b *model.Book) (*model.Book, error) {
	if b == nil {
		return nil, ErrInvalidArgument
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	cp := *b
	cp.ID = r.nextID
	r.nextID++
	r.books[cp.ID] = &cp
	res := cp
	return &res, nil
}

func (r *BookRepository) Update(id int64, b *model.Book) (*model.Book, error) {
	if id <= 0 || b == nil {
		return nil, ErrInvalidArgument
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	existing, ok := r.books[id]
	if !ok {
		return nil, ErrNotFound
	}
	existing.Title = b.Title
	existing.Author = b.Author
	existing.Stock = b.Stock
	cp := *existing
	return &cp, nil
}

func (r *BookRepository) Delete(id int64) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, ok := r.books[id]; !ok {
		return ErrNotFound
	}
	delete(r.books, id)
	return nil
}

func (r *BookRepository) DeleteByID(id int64) error {
	if id <= 0 {
		return ErrInvalidArgument
	}
	return r.Delete(id)
}

func (r *BookRepository) UpdateStock(id int64, delta int) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidArgument
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	b, ok := r.books[id]
	if !ok {
		return nil, ErrNotFound
	}
	if b.Stock+delta < 0 {
		return nil, ErrInvalidArgument
	}
	b.Stock += delta
	cp := *b
	return &cp, nil
}

func (r *BookRepository) SetStock(id int64, stock int) (*model.Book, error) {
	if id <= 0 {
		return nil, ErrInvalidArgument
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	b, ok := r.books[id]
	if !ok {
		return nil, ErrNotFound
	}
	if stock < 0 {
		return nil, ErrInvalidArgument
	}
	b.Stock = stock
	cp := *b
	return &cp, nil
}

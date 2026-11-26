package repository

import (
	"context"
	"errors"

	"example.com/autocode/internal/model"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const DefaultDatabaseURL = "postgresql://postgres:postgres@localhost:5435/ai_test"

const booksSchema = `
CREATE TABLE IF NOT EXISTS books (
	id BIGSERIAL PRIMARY KEY,
	title TEXT NOT NULL,
	author TEXT NOT NULL DEFAULT '',
	stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
`

var ErrNotFound = errors.New("book not found")

type BookRepository struct {
	pool *pgxpool.Pool
}

func NewBookRepository(ctx context.Context, databaseURL string) (*BookRepository, error) {
	if databaseURL == "" {
		databaseURL = DefaultDatabaseURL
	}
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	if _, err := pool.Exec(ctx, booksSchema); err != nil {
		pool.Close()
		return nil, err
	}
	return &BookRepository{pool: pool}, nil
}

func (r *BookRepository) Close() {
	if r != nil && r.pool != nil {
		r.pool.Close()
	}
}

func scanBook(row pgx.Row) (*model.Book, error) {
	var b model.Book
	err := row.Scan(&b.ID, &b.Title, &b.Author, &b.Stock)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return &b, nil
}

func (r *BookRepository) List(ctx context.Context) ([]*model.Book, error) {
	rows, err := r.pool.Query(ctx, `SELECT id, title, author, stock FROM books ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]*model.Book, 0)
	for rows.Next() {
		var b model.Book
		if err := rows.Scan(&b.ID, &b.Title, &b.Author, &b.Stock); err != nil {
			return nil, err
		}
		out = append(out, &b)
	}
	return out, rows.Err()
}

func (r *BookRepository) Get(ctx context.Context, id int64) (*model.Book, error) {
	return scanBook(r.pool.QueryRow(ctx,
		`SELECT id, title, author, stock FROM books WHERE id = $1`, id))
}

func (r *BookRepository) Create(ctx context.Context, title, author string, stock int) (*model.Book, error) {
	return scanBook(r.pool.QueryRow(ctx,
		`INSERT INTO books (title, author, stock)
		 VALUES ($1, $2, $3)
		 RETURNING id, title, author, stock`,
		title, author, stock))
}

func (r *BookRepository) Update(ctx context.Context, id int64, title, author string, stock int) (*model.Book, error) {
	return scanBook(r.pool.QueryRow(ctx,
		`UPDATE books
		 SET title = $2, author = $3, stock = $4, updated_at = NOW()
		 WHERE id = $1
		 RETURNING id, title, author, stock`,
		id, title, author, stock))
}

func (r *BookRepository) SetStock(ctx context.Context, id int64, stock int) (*model.Book, error) {
	return scanBook(r.pool.QueryRow(ctx,
		`UPDATE books
		 SET stock = $2, updated_at = NOW()
		 WHERE id = $1
		 RETURNING id, title, author, stock`,
		id, stock))
}

func (r *BookRepository) Delete(ctx context.Context, id int64) error {
	tag, err := r.pool.Exec(ctx, `DELETE FROM books WHERE id = $1`, id)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

const defaultDatabaseURL = "postgresql://postgres:postgres@localhost:5435/ai_test"

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

type Book struct {
	ID     int64  `json:"id"`
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type bookRequest struct {
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type stockRequest struct {
	Stock *int `json:"stock"`
}

// 统一响应：成功 {code:0,message,data}；失败 {code:<http>,message,error:<码>}
type apiResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Error   string `json:"error,omitempty"`
	Data    any    `json:"data,omitempty"`
}

type apiError struct {
	status  int
	code    string
	message string
}

func (e *apiError) Error() string { return e.message }

var (
	errValidation = &apiError{http.StatusBadRequest, "VALIDATION_ERROR", "请求参数非法"}
	errInvalidID  = &apiError{http.StatusBadRequest, "VALIDATION_ERROR", "图书 id 必须为大于 0 的整数"}
	errNotFound   = &apiError{http.StatusNotFound, "NOT_FOUND", "图书不存在"}
	errInternal   = &apiError{http.StatusInternalServerError, "INTERNAL_ERROR", "服务内部错误"}
)

type Store struct {
	pool *pgxpool.Pool
}

func NewStore(ctx context.Context, databaseURL string) (*Store, error) {
	if databaseURL == "" {
		databaseURL = defaultDatabaseURL
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
	return &Store{pool: pool}, nil
}

func (s *Store) Close() {
	if s != nil && s.pool != nil {
		s.pool.Close()
	}
}

func scanBook(row pgx.Row) (*Book, error) {
	var b Book
	err := row.Scan(&b.ID, &b.Title, &b.Author, &b.Stock)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, errNotFound
		}
		return nil, err
	}
	return &b, nil
}

func mapStoreError(err error) error {
	if err == nil {
		return nil
	}
	var ae *apiError
	if errors.As(err, &ae) {
		return ae
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23514" {
		return errValidation
	}
	log.Printf("store error: %v", err)
	return errInternal
}

func (s *Store) List() ([]*Book, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT id, title, author, stock FROM books ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]*Book, 0)
	for rows.Next() {
		var b Book
		if err := rows.Scan(&b.ID, &b.Title, &b.Author, &b.Stock); err != nil {
			return nil, err
		}
		out = append(out, &b)
	}
	return out, rows.Err()
}

func (s *Store) Get(id int64) (*Book, error) {
	return scanBook(s.pool.QueryRow(context.Background(),
		`SELECT id, title, author, stock FROM books WHERE id = $1`, id))
}

func validateBook(req bookRequest) (string, string, error) {
	title := strings.TrimSpace(req.Title)
	author := strings.TrimSpace(req.Author)
	if title == "" || req.Stock < 0 {
		return "", "", errValidation
	}
	return title, author, nil
}

func (s *Store) Create(req bookRequest) (*Book, error) {
	title, author, err := validateBook(req)
	if err != nil {
		return nil, err
	}
	return scanBook(s.pool.QueryRow(context.Background(),
		`INSERT INTO books (title, author, stock)
		 VALUES ($1, $2, $3)
		 RETURNING id, title, author, stock`,
		title, author, req.Stock))
}

func (s *Store) Update(id int64, req bookRequest) (*Book, error) {
	title, author, err := validateBook(req)
	if err != nil {
		return nil, err
	}
	return scanBook(s.pool.QueryRow(context.Background(),
		`UPDATE books
		 SET title = $2, author = $3, stock = $4, updated_at = NOW()
		 WHERE id = $1
		 RETURNING id, title, author, stock`,
		id, title, author, req.Stock))
}

func (s *Store) SetStock(id int64, stock int) (*Book, error) {
	if stock < 0 {
		return nil, errValidation
	}
	return scanBook(s.pool.QueryRow(context.Background(),
		`UPDATE books
		 SET stock = $2, updated_at = NOW()
		 WHERE id = $1
		 RETURNING id, title, author, stock`,
		id, stock))
}

func (s *Store) Delete(id int64) error {
	tag, err := s.pool.Exec(context.Background(), `DELETE FROM books WHERE id = $1`, id)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return errNotFound
	}
	return nil
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

func writeSuccess(w http.ResponseWriter, status int, message string, data any) {
	writeJSON(w, status, apiResponse{Code: 0, Message: message, Data: data})
}

func writeError(w http.ResponseWriter, err error) {
	var ae *apiError
	if !errors.As(err, &ae) {
		log.Printf("internal error: %v", err)
		ae = errInternal
	}
	writeJSON(w, ae.status, apiResponse{Code: ae.status, Message: ae.message, Error: ae.code})
}

func parseID(r *http.Request) (int64, error) {
	raw := r.PathValue("id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || id <= 0 {
		return 0, errInvalidID
	}
	return id, nil
}

func decodeBody(r *http.Request, v interface{}) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return errValidation
	}
	return nil
}

func cors(next http.Handler) http.Handler {
	allowed := map[string]bool{
		"http://localhost:5173": true,
		"http://localhost:5174": true,
		"http://localhost:5175": true,
		"http://127.0.0.1:5173": true,
		"http://127.0.0.1:5174": true,
		"http://127.0.0.1:5175": true,
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if allowed[origin] {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func main() {
	ctx := context.Background()
	store, err := NewStore(ctx, os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatalf("connect database: %v", err)
	}
	defer store.Close()

	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	mux.HandleFunc("GET /api/books", func(w http.ResponseWriter, r *http.Request) {
		books, err := store.List()
		if err != nil {
			writeError(w, mapStoreError(err))
			return
		}
		writeSuccess(w, http.StatusOK, "ok", books)
	})

	mux.HandleFunc("POST /api/books", func(w http.ResponseWriter, r *http.Request) {
		var req bookRequest
		if err := decodeBody(r, &req); err != nil {
			writeError(w, err)
			return
		}
		book, err := store.Create(req)
		if err != nil {
			writeError(w, mapStoreError(err))
			return
		}
		writeSuccess(w, http.StatusCreated, "created", book)
	})

	mux.HandleFunc("GET /api/books/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, err)
			return
		}
		book, err := store.Get(id)
		if err != nil {
			writeError(w, mapStoreError(err))
			return
		}
		writeSuccess(w, http.StatusOK, "ok", book)
	})

	mux.HandleFunc("PUT /api/books/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, err)
			return
		}
		var req bookRequest
		if err := decodeBody(r, &req); err != nil {
			writeError(w, err)
			return
		}
		book, err := store.Update(id, req)
		if err != nil {
			writeError(w, mapStoreError(err))
			return
		}
		writeSuccess(w, http.StatusOK, "ok", book)
	})

	mux.HandleFunc("DELETE /api/books/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, err)
			return
		}
		if err := store.Delete(id); err != nil {
			writeError(w, mapStoreError(err))
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	mux.HandleFunc("PATCH /api/books/{id}/stock", func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, err)
			return
		}
		var req stockRequest
		if err := decodeBody(r, &req); err != nil {
			writeError(w, err)
			return
		}
		if req.Stock == nil || *req.Stock < 0 {
			writeError(w, errValidation)
			return
		}
		book, err := store.SetStock(id, *req.Stock)
		if err != nil {
			writeError(w, mapStoreError(err))
			return
		}
		writeSuccess(w, http.StatusOK, "ok", book)
	})

	// 业务前端在 auto_code/frontend（Vite 5175）；根路径仅作可选占位
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "ok",
			"message": "autocode book API; UI at Vite :5175",
		})
	})

	addr := "127.0.0.1:8072"
	log.Printf("listening on http://%s", addr)
	if err := http.ListenAndServe(addr, cors(mux)); err != nil {
		log.Fatal(err)
	}
}

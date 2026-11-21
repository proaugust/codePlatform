package main

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Book struct {
	ID        int64     `json:"id"`
	Title     string    `json:"title"`
	Author    string    `json:"author"`
	ISBN      string    `json:"isbn"`
	Stock     int       `json:"stock"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type createBookRequest struct {
	Title  string `json:"title"`
	Author string `json:"author"`
	ISBN   string `json:"isbn"`
	Stock  int    `json:"stock"`
}

type stockRequest struct {
	Stock *int `json:"stock"`
}

type ErrorResponse struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	Path      string `json:"path"`
	Timestamp string `json:"timestamp"`
}

type apiError struct {
	status  int
	code    string
	message string
}

func (e *apiError) Error() string { return e.message }

var (
	errBadRequest   = &apiError{http.StatusBadRequest, "BAD_REQUEST", "请求参数非法"}
	errNotFound     = &apiError{http.StatusNotFound, "BOOK_NOT_FOUND", "图书不存在"}
	errConflict     = &apiError{http.StatusConflict, "ISBN_CONFLICT", "ISBN 已存在"}
	errMethodNotAll = &apiError{http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "方法不支持"}
	errInternal     = &apiError{http.StatusInternalServerError, "INTERNAL_ERROR", "服务内部错误"}
)

type Store struct {
	mu     sync.RWMutex
	books  map[int64]*Book
	isbn   map[string]int64
	nextID int64
}

func NewStore() *Store {
	return &Store{books: make(map[int64]*Book), isbn: make(map[string]int64), nextID: 1}
}

func (s *Store) List(keyword string) []*Book {
	s.mu.RLock()
	defer s.mu.RUnlock()
	kw := strings.ToLower(strings.TrimSpace(keyword))
	out := make([]*Book, 0, len(s.books))
	for _, b := range s.books {
		if kw == "" || strings.Contains(strings.ToLower(b.Title), kw) ||
			strings.Contains(strings.ToLower(b.Author), kw) ||
			strings.Contains(strings.ToLower(b.ISBN), kw) {
			cp := *b
			out = append(out, &cp)
		}
	}
	return out
}

func (s *Store) Get(id int64) (*Book, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	b, ok := s.books[id]
	if !ok {
		return nil, errNotFound
	}
	cp := *b
	return &cp, nil
}

func (s *Store) Create(req createBookRequest) (*Book, error) {
	title := strings.TrimSpace(req.Title)
	author := strings.TrimSpace(req.Author)
	isbn := strings.TrimSpace(req.ISBN)
	if title == "" || author == "" || isbn == "" || req.Stock < 0 {
		return nil, errBadRequest
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.isbn[isbn]; exists {
		return nil, errConflict
	}
	now := time.Now().UTC()
	b := &Book{ID: s.nextID, Title: title, Author: author, ISBN: isbn, Stock: req.Stock, CreatedAt: now, UpdatedAt: now}
	s.nextID++
	s.books[b.ID] = b
	s.isbn[isbn] = b.ID
	cp := *b
	return &cp, nil
}

func (s *Store) UpdateStock(id int64, stock int) (*Book, error) {
	if stock < 0 {
		return nil, errBadRequest
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	b, ok := s.books[id]
	if !ok {
		return nil, errNotFound
	}
	b.Stock = stock
	b.UpdatedAt = time.Now().UTC()
	cp := *b
	return &cp, nil
}

func (s *Store) Delete(id int64) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	b, ok := s.books[id]
	if !ok {
		return errNotFound
	}
	delete(s.books, id)
	delete(s.isbn, b.ISBN)
	return nil
}

type Server struct {
	store *Store
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

func writeError(w http.ResponseWriter, r *http.Request, err error) {
	ae := errInternal
	var target *apiError
	if errors.As(err, &target) {
		ae = target
	}
	writeJSON(w, ae.status, ErrorResponse{
		Code:      ae.code,
		Message:   ae.message,
		Path:      r.URL.Path,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func decodeBody(w http.ResponseWriter, r *http.Request, dst interface{}) error {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(dst); err != nil {
		return errBadRequest
	}
	return nil
}

func parseID(r *http.Request) (int64, error) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		return 0, errBadRequest
	}
	return id, nil
}

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) listBooks(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.store.List(r.URL.Query().Get("keyword")))
}

func (s *Server) getBook(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, r, err)
		return
	}
	b, err := s.store.Get(id)
	if err != nil {
		writeError(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, b)
}

func (s *Server) createBook(w http.ResponseWriter, r *http.Request) {
	var req createBookRequest
	if err := decodeBody(w, r, &req); err != nil {
		writeError(w, r, err)
		return
	}
	b, err := s.store.Create(req)
	if err != nil {
		writeError(w, r, err)
		return
	}
	writeJSON(w, http.StatusCreated, b)
}

func (s *Server) updateStock(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, r, err)
		return
	}
	var req stockRequest
	if err := decodeBody(w, r, &req); err != nil {
		writeError(w, r, err)
		return
	}
	if req.Stock == nil {
		writeError(w, r, errBadRequest)
		return
	}
	b, err := s.store.UpdateStock(id, *req.Stock)
	if err != nil {
		writeError(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, b)
}

func (s *Server) deleteBook(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, r, err)
		return
	}
	if err := s.store.Delete(id); err != nil {
		writeError(w, r, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

var allowedOrigins = map[string]bool{
	"http://localhost:5173": true, "http://localhost:5174": true, "http://localhost:5175": true,
	"http://127.0.0.1:5173": true, "http://127.0.0.1:5174": true, "http://127.0.0.1:5175": true,
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if allowedOrigins[origin] {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Access-Control-Max-Age", "86400")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func recoverer(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("panic: %v", rec)
				writeError(w, r, errInternal)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func main() {
	srv := &Server{store: NewStore()}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", srv.health)
	mux.HandleFunc("GET /{$}", srv.health)
	mux.HandleFunc("GET /api/books", srv.listBooks)
	mux.HandleFunc("POST /api/books", srv.createBook)
	mux.HandleFunc("GET /api/books/{id}", srv.getBook)
	mux.HandleFunc("DELETE /api/books/{id}", srv.deleteBook)
	mux.HandleFunc("PATCH /api/books/{id}/stock", srv.updateStock)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		writeError(w, r, errNotFound)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8072"
	}
	addr := ":" + port
	handler := recoverer(cors(mux))
	log.Printf("book api listening on %s", addr)
	if err := http.ListenAndServe(addr, handler); err != nil {
		log.Fatal(err)
	}
}

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
)

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

type errorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type errorEnvelope struct {
	Error errorBody `json:"error"`
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
	mu     sync.RWMutex
	books  map[int64]*Book
	nextID int64
}

func NewStore() *Store {
	return &Store{books: make(map[int64]*Book), nextID: 1}
}

func (s *Store) List() []*Book {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*Book, 0, len(s.books))
	for _, b := range s.books {
		cp := *b
		out = append(out, &cp)
	}
	for i := 0; i < len(out); i++ {
		for j := i + 1; j < len(out); j++ {
			if out[j].ID < out[i].ID {
				out[i], out[j] = out[j], out[i]
			}
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
	s.mu.Lock()
	defer s.mu.Unlock()
	b := &Book{ID: s.nextID, Title: title, Author: author, Stock: req.Stock}
	s.books[b.ID] = b
	s.nextID++
	cp := *b
	return &cp, nil
}

func (s *Store) Update(id int64, req bookRequest) (*Book, error) {
	title, author, err := validateBook(req)
	if err != nil {
		return nil, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	b, ok := s.books[id]
	if !ok {
		return nil, errNotFound
	}
	b.Title = title
	b.Author = author
	b.Stock = req.Stock
	cp := *b
	return &cp, nil
}

func (s *Store) SetStock(id int64, stock int) (*Book, error) {
	if stock < 0 {
		return nil, errValidation
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	b, ok := s.books[id]
	if !ok {
		return nil, errNotFound
	}
	b.Stock = stock
	cp := *b
	return &cp, nil
}

func (s *Store) Delete(id int64) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.books[id]; !ok {
		return errNotFound
	}
	delete(s.books, id)
	return nil
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

func writeError(w http.ResponseWriter, err error) {
	var ae *apiError
	if !errors.As(err, &ae) {
		log.Printf("internal error: %v", err)
		ae = errInternal
	}
	writeJSON(w, ae.status, errorEnvelope{Error: errorBody{Code: ae.code, Message: ae.message}})
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
	store := NewStore()
	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	mux.HandleFunc("GET /api/books", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, store.List())
	})

	mux.HandleFunc("POST /api/books", func(w http.ResponseWriter, r *http.Request) {
		var req bookRequest
		if err := decodeBody(r, &req); err != nil {
			writeError(w, err)
			return
		}
		b, err := store.Create(req)
		if err != nil {
			writeError(w, err)
			return
		}
		writeJSON(w, http.StatusCreated, b)
	})

	mux.HandleFunc("GET /api/books/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, err)
			return
		}
		b, err := store.Get(id)
		if err != nil {
			writeError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, b)
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
		b, err := store.Update(id, req)
		if err != nil {
			writeError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, b)
	})

	mux.HandleFunc("DELETE /api/books/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := parseID(r)
		if err != nil {
			writeError(w, err)
			return
		}
		if err := store.Delete(id); err != nil {
			writeError(w, err)
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
		if req.Stock == nil {
			writeError(w, errValidation)
			return
		}
		b, err := store.SetStock(id, *req.Stock)
		if err != nil {
			writeError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, b)
	})

	staticDir := "static"
	if _, err := os.Stat(staticDir); err == nil {
		mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.Dir(staticDir))))
	}

	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		path := staticDir + "/index.html"
		if _, err := os.Stat(path); err != nil {
			writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "message": "autocode book service"})
			return
		}
		http.ServeFile(w, r, path)
	})

	addr := ":8072"
	log.Printf("listening on %s", addr)
	if err := http.ListenAndServe(addr, cors(mux)); err != nil {
		log.Fatal(err)
	}
}

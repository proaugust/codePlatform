package handler

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"example.com/autocode/internal/service"
)

type BookHandler struct {
	svc *service.BookService
}

func NewBookHandler(svc *service.BookService) *BookHandler {
	return &BookHandler{svc: svc}
}

func (h *BookHandler) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/books", h.List)
	mux.HandleFunc("POST /api/books", h.Create)
	mux.HandleFunc("GET /api/books/{id}", h.Get)
	mux.HandleFunc("DELETE /api/books/{id}", h.Delete)
	mux.HandleFunc("PATCH /api/books/{id}/stock", h.UpdateStock)
}

type createBookRequest struct {
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type updateStockRequest struct {
	Delta int `json:"delta"`
}

func (h *BookHandler) List(w http.ResponseWriter, r *http.Request) {
	books, err := h.svc.ListBooks()
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": books})
}

func (h *BookHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req createBookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_ARGUMENT", "invalid request body")
		return
	}
	book, err := h.svc.CreateBook(req.Title, req.Author, req.Stock)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"data": book})
}

func (h *BookHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r)
	if !ok {
		return
	}
	book, err := h.svc.GetBook(id)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": book})
}

func (h *BookHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r)
	if !ok {
		return
	}
	if err := h.svc.DeleteBook(id); err != nil {
		writeServiceError(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *BookHandler) UpdateStock(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r)
	if !ok {
		return
	}
	var req updateStockRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_ARGUMENT", "invalid request body")
		return
	}
	book, err := h.svc.UpdateStock(id, req.Delta)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": book})
}

func parseID(w http.ResponseWriter, r *http.Request) (int, bool) {
	raw := r.PathValue("id")
	id, err := strconv.Atoi(raw)
	if err != nil || id <= 0 {
		writeError(w, http.StatusBadRequest, "INVALID_ID", "invalid book id")
		return 0, false
	}
	return id, true
}

func writeServiceError(w http.ResponseWriter, err error) {
	var se *service.Error
	if errors.As(err, &se) {
		switch se.Code {
		case service.CodeNotFound:
			writeError(w, http.StatusNotFound, "NOT_FOUND", se.Message)
			return
		case service.CodeInvalidArgument:
			writeError(w, http.StatusBadRequest, "INVALID_ARGUMENT", se.Message)
			return
		}
	}
	writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", "internal server error")
}

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
	mux.HandleFunc("PUT /api/books/{id}", h.Update)
	mux.HandleFunc("DELETE /api/books/{id}", h.Delete)
	mux.HandleFunc("PATCH /api/books/{id}/stock", h.UpdateStock)
}

type createBookRequest struct {
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type updateBookRequest struct {
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type updateStockRequest struct {
	Stock *int `json:"stock"`
	Delta *int `json:"delta"`
}

func (h *BookHandler) List(w http.ResponseWriter, r *http.Request) {
	books, err := h.svc.ListBooks()
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "success", books)
}

func (h *BookHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req createBookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", "invalid request body")
		return
	}
	book, err := h.svc.CreateBook(req.Title, req.Author, req.Stock)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeSuccess(w, http.StatusCreated, "success", book)
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
	writeSuccess(w, http.StatusOK, "success", book)
}

func (h *BookHandler) Update(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r)
	if !ok {
		return
	}
	var req updateBookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", "invalid request body")
		return
	}
	book, err := h.svc.UpdateBook(id, req.Title, req.Author, req.Stock)
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "success", book)
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
		writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", "invalid request body")
		return
	}
	var (
		book any
		err  error
	)
	switch {
	case req.Stock != nil:
		book, err = h.svc.SetStock(id, *req.Stock)
	case req.Delta != nil:
		book, err = h.svc.UpdateStock(id, *req.Delta)
	default:
		writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", "stock or delta required")
		return
	}
	if err != nil {
		writeServiceError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "success", book)
}

func parseID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	raw := r.PathValue("id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || id <= 0 {
		writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", "图书 id 必须为大于 0 的整数")
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
			writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", se.Message)
			return
		}
	}
	writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", "internal server error")
}

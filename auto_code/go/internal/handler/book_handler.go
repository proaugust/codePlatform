package handler

import (
	"net/http"

	"example.com/autocode/internal/model"
	"example.com/autocode/internal/service"
)

type BookHandler struct {
	svc *service.BookService
}

func NewBookHandler(svc *service.BookService) *BookHandler {
	return &BookHandler{svc: svc}
}

func (h *BookHandler) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /health", h.Health)
	mux.HandleFunc("GET /api/books", h.List)
	mux.HandleFunc("POST /api/books", h.Create)
	mux.HandleFunc("GET /api/books/{id}", h.Get)
	mux.HandleFunc("PUT /api/books/{id}", h.Update)
	mux.HandleFunc("DELETE /api/books/{id}", h.Delete)
	mux.HandleFunc("PATCH /api/books/{id}/stock", h.UpdateStock)
	mux.HandleFunc("GET /{$}", h.Root)
}

func (h *BookHandler) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (h *BookHandler) Root(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"message": "autocode book API; UI at Vite :5175",
	})
}

func (h *BookHandler) List(w http.ResponseWriter, r *http.Request) {
	books, err := h.svc.List(r.Context())
	if err != nil {
		writeError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "ok", books)
}

func (h *BookHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req model.BookRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, err)
		return
	}
	book, err := h.svc.Create(r.Context(), req)
	if err != nil {
		writeError(w, err)
		return
	}
	writeSuccess(w, http.StatusCreated, "created", book)
}

func (h *BookHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	book, err := h.svc.Get(r.Context(), id)
	if err != nil {
		writeError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "ok", book)
}

func (h *BookHandler) Update(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	var req model.BookRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, err)
		return
	}
	book, err := h.svc.Update(r.Context(), id, req)
	if err != nil {
		writeError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "ok", book)
}

func (h *BookHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	if err := h.svc.Delete(r.Context(), id); err != nil {
		writeError(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *BookHandler) UpdateStock(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	var req model.StockRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, err)
		return
	}
	if req.Stock == nil || *req.Stock < 0 {
		writeError(w, service.ErrValidation)
		return
	}
	book, err := h.svc.SetStock(r.Context(), id, *req.Stock)
	if err != nil {
		writeError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, "ok", book)
}

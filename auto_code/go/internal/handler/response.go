package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strconv"

	"example.com/autocode/internal/service"
)

type apiResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Error   string `json:"error,omitempty"`
	Data    any    `json:"data,omitempty"`
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
	var ae *service.ApiError
	if !errors.As(err, &ae) {
		log.Printf("internal error: %v", err)
		ae = service.ErrInternal
	}
	writeJSON(w, ae.Status, apiResponse{Code: ae.Status, Message: ae.Message, Error: ae.Code})
}

func parseID(r *http.Request) (int64, error) {
	raw := r.PathValue("id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || id <= 0 {
		return 0, service.ErrInvalidID
	}
	return id, nil
}

func decodeBody(r *http.Request, v interface{}) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return service.ErrValidation
	}
	return nil
}

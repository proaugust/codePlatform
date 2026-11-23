package handler

import (
	"encoding/json"
	"net/http"
)

type apiResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Error   string `json:"error,omitempty"`
	Data    any    `json:"data,omitempty"`
}

const (
	CodeValidationError = "VALIDATION_ERROR"
	CodeNotFound        = "NOT_FOUND"
	CodeInternalError   = "INTERNAL_ERROR"
)

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v == nil {
		return
	}
	_ = json.NewEncoder(w).Encode(v)
}

func writeSuccess(w http.ResponseWriter, status int, message string, data any) {
	writeJSON(w, status, apiResponse{Code: 0, Message: message, Data: data})
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, apiResponse{Code: status, Message: message, Error: code})
}

func writeValidationError(w http.ResponseWriter, message string) {
	writeError(w, http.StatusBadRequest, CodeValidationError, message)
}

func writeNotFound(w http.ResponseWriter, message string) {
	writeError(w, http.StatusNotFound, CodeNotFound, message)
}

func writeInternalError(w http.ResponseWriter, message string) {
	writeError(w, http.StatusInternalServerError, CodeInternalError, message)
}

func writeNoContent(w http.ResponseWriter) {
	w.WriteHeader(http.StatusNoContent)
}

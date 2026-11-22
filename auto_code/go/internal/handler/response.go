package handler

import (
	"encoding/json"
	"net/http"
)

type errorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v == nil {
		return
	}
	_ = json.NewEncoder(w).Encode(v)
}

func writeSuccess(w http.ResponseWriter, status int, v any) {
	writeJSON(w, status, v)
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, errorBody{Code: code, Message: message})
}

func writeMessage(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"message": message})
}

func writeValidationError(w http.ResponseWriter, message string) {
	if message == "" {
		message = "参数校验失败"
	}
	writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", message)
}

func writeNotFound(w http.ResponseWriter, message string) {
	if message == "" {
		message = "资源不存在"
	}
	writeError(w, http.StatusNotFound, "NOT_FOUND", message)
}

func writeInternalError(w http.ResponseWriter, message string) {
	if message == "" {
		message = "服务内部错误"
	}
	writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", message)
}

func writeNoContent(w http.ResponseWriter) {
	w.WriteHeader(http.StatusNoContent)
}

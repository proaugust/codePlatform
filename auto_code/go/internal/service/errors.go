package service

import (
	"errors"
	"fmt"
	"net/http"
)

// Code is a stable machine-readable error code.
type Code string

const (
	CodeInvalidID        Code = "INVALID_ID"
	CodeInvalidArgument  Code = "INVALID_ARGUMENT"
	CodeNotFound         Code = "NOT_FOUND"
	CodeMethodNotAllowed Code = "METHOD_NOT_ALLOWED"
	CodeInternal         Code = "INTERNAL_ERROR"
)

// Error is a business error carrying a code and HTTP status.
type Error struct {
	Code    Code
	Message string
	Status  int
}

func (e *Error) Error() string { return e.Message }

func NewError(code Code, status int, format string, args ...any) *Error {
	return &Error{Code: code, Message: fmt.Sprintf(format, args...), Status: status}
}

// Sentinel errors for errors.Is comparisons.
var (
	ErrInvalidID       = &Error{Code: CodeInvalidID, Message: "invalid id", Status: http.StatusBadRequest}
	ErrInvalidArgument = &Error{Code: CodeInvalidArgument, Message: "invalid argument", Status: http.StatusBadRequest}
	ErrNotFound        = &Error{Code: CodeNotFound, Message: "not found", Status: http.StatusNotFound}
	ErrInternal        = &Error{Code: CodeInternal, Message: "internal error", Status: http.StatusInternalServerError}
)

// Is supports errors.Is by comparing codes.
func (e *Error) Is(target error) bool {
	t, ok := target.(*Error)
	if !ok {
		return false
	}
	return e.Code == t.Code
}

func NewInvalidID(format string, args ...any) *Error {
	return NewError(CodeInvalidID, http.StatusBadRequest, format, args...)
}

func NewInvalidArgument(format string, args ...any) *Error {
	return NewError(CodeInvalidArgument, http.StatusBadRequest, format, args...)
}

func NewNotFound(format string, args ...any) *Error {
	return NewError(CodeNotFound, http.StatusNotFound, format, args...)
}

func NewInternal(format string, args ...any) *Error {
	return NewError(CodeInternal, http.StatusInternalServerError, format, args...)
}

// AsError converts any error into a *Error, defaulting to INTERNAL_ERROR.
func AsError(err error) *Error {
	if err == nil {
		return nil
	}
	var e *Error
	if errors.As(err, &e) {
		return e
	}
	return NewInternal("%s", err.Error())
}

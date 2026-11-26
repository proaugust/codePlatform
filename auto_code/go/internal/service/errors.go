package service

import "net/http"

// ApiError 统一业务错误：成功 {code:0,...}；失败 {code:<http>,message,error:<码>}
type ApiError struct {
	Status  int
	Code    string
	Message string
}

func (e *ApiError) Error() string { return e.Message }

var (
	ErrValidation = &ApiError{http.StatusBadRequest, "VALIDATION_ERROR", "请求参数非法"}
	ErrInvalidID  = &ApiError{http.StatusBadRequest, "VALIDATION_ERROR", "图书 id 必须为大于 0 的整数"}
	ErrNotFound   = &ApiError{http.StatusNotFound, "NOT_FOUND", "图书不存在"}
	ErrInternal   = &ApiError{http.StatusInternalServerError, "INTERNAL_ERROR", "服务内部错误"}
)

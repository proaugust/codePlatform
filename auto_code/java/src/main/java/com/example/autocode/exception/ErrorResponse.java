package com.example.autocode.exception;

import java.time.LocalDateTime;

public record ErrorResponse(
    String code,
    String message,
    String path,
    LocalDateTime timestamp
) {
}

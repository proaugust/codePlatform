package com.example.autocode.dto;

import com.example.autocode.entity.Book;

import java.time.LocalDateTime;

public record BookResponse(
    Long id,
    String title,
    String author,
    String isbn,
    Integer stock,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {

    public static BookResponse from(Book book) {
        return new BookResponse(
            book.getId(),
            book.getTitle(),
            book.getAuthor(),
            book.getIsbn(),
            book.getStock(),
            book.getCreatedAt(),
            book.getUpdatedAt()
        );
    }
}

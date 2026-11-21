package com.example.autocode.service;

import com.example.autocode.dto.BookResponse;
import com.example.autocode.dto.CreateBookRequest;
import com.example.autocode.dto.UpdateStockRequest;
import com.example.autocode.entity.Book;
import com.example.autocode.exception.BusinessException;
import com.example.autocode.repository.BookRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class BookService {

    private final BookRepository bookRepository;

    public BookService(BookRepository bookRepository) {
        this.bookRepository = bookRepository;
    }

    @Transactional(readOnly = true)
    public List<BookResponse> listBooks(String keyword) {
        List<Book> books;
        if (keyword == null || keyword.isBlank()) {
            books = bookRepository.findAllByOrderByIdAsc();
        } else {
            String value = keyword.trim();
            books = bookRepository
                .findByTitleContainingIgnoreCaseOrAuthorContainingIgnoreCaseOrIsbnContainingIgnoreCaseOrderByIdAsc(
                    value, value, value);
        }
        return books.stream().map(BookResponse::from).toList();
    }

    @Transactional(readOnly = true)
    public BookResponse getById(Long id) {
        validateId(id);
        Book book = bookRepository.findById(id)
            .orElseThrow(() -> new BusinessException(HttpStatus.NOT_FOUND, "BOOK_NOT_FOUND", "图书不存在"));
        return BookResponse.from(book);
    }

    @Transactional
    public BookResponse create(CreateBookRequest request) {
        String isbn = request.getIsbn() == null ? null : request.getIsbn().trim();
        if (isbn == null || isbn.isBlank()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "isbn 不能为空");
        }
        if (bookRepository.existsByIsbn(isbn)) {
            throw new BusinessException(HttpStatus.CONFLICT, "ISBN_ALREADY_EXISTS", "ISBN 已存在");
        }

        int stock = request.getStock() == null ? 0 : request.getStock();
        if (stock < 0) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "库存不能为负数");
        }

        Book book = new Book();
        book.setTitle(request.getTitle() == null ? null : request.getTitle().trim());
        book.setAuthor(request.getAuthor() == null ? null : request.getAuthor().trim());
        book.setIsbn(isbn);
        book.setStock(stock);

        Book saved = bookRepository.saveAndFlush(book);
        return BookResponse.from(saved);
    }

    @Transactional
    public BookResponse updateStock(Long id, UpdateStockRequest request) {
        validateId(id);
        if (request.getStock() == null) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "stock 不能为空");
        }
        if (request.getStock() < 0) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "库存不能为负数");
        }

        Book book = bookRepository.findById(id)
            .orElseThrow(() -> new BusinessException(HttpStatus.NOT_FOUND, "BOOK_NOT_FOUND", "图书不存在"));
        book.setStock(request.getStock());

        Book saved = bookRepository.saveAndFlush(book);
        return BookResponse.from(saved);
    }

    private void validateId(Long id) {
        if (id == null || id <= 0) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "id 必须大于 0");
        }
    }
}

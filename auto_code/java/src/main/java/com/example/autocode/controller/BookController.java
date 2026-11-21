package com.example.autocode.controller;

import com.example.autocode.dto.BookResponse;
import com.example.autocode.dto.CreateBookRequest;
import com.example.autocode.dto.UpdateStockRequest;
import com.example.autocode.service.BookService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.List;

@RestController
@RequestMapping("/api/books")
public class BookController {

    private final BookService bookService;

    public BookController(BookService bookService) {
        this.bookService = bookService;
    }

    @GetMapping
    public List<BookResponse> listBooks(@RequestParam(name = "keyword", required = false) String keyword) {
        return bookService.listBooks(keyword);
    }

    @GetMapping("/{id}")
    public BookResponse getBook(@PathVariable("id") Long id) {
        return bookService.getById(id);
    }

    @PostMapping
    public ResponseEntity<BookResponse> createBook(@Valid @RequestBody CreateBookRequest request) {
        BookResponse response = bookService.create(request);
        return ResponseEntity.created(URI.create("/api/books/" + response.id())).body(response);
    }

    @PatchMapping("/{id}/stock")
    public BookResponse updateStock(@PathVariable("id") Long id,
                                    @Valid @RequestBody UpdateStockRequest request) {
        return bookService.updateStock(id, request);
    }
}

package com.example.autocode.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class CreateBookRequest {

    @NotBlank(message = "title 不能为空")
    @Size(max = 200, message = "title 长度不能超过 200 个字符")
    private String title;

    @NotBlank(message = "author 不能为空")
    @Size(max = 120, message = "author 长度不能超过 120 个字符")
    private String author;

    @NotBlank(message = "isbn 不能为空")
    @Size(max = 20, message = "isbn 长度不能超过 20 个字符")
    private String isbn;

    @Min(value = 0, message = "stock 不能为负数")
    private Integer stock;

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getAuthor() {
        return author;
    }

    public void setAuthor(String author) {
        this.author = author;
    }

    public String getIsbn() {
        return isbn;
    }

    public void setIsbn(String isbn) {
        this.isbn = isbn;
    }

    public Integer getStock() {
        return stock;
    }

    public void setStock(Integer stock) {
        this.stock = stock;
    }
}

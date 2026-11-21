package com.example.autocode.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public class UpdateStockRequest {

    @NotNull(message = "stock 不能为空")
    @Min(value = 0, message = "stock 不能为负数")
    private Integer stock;

    public Integer getStock() {
        return stock;
    }

    public void setStock(Integer stock) {
        this.stock = stock;
    }
}

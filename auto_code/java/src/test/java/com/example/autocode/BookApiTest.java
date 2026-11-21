// package com.example.autocode;

// import com.fasterxml.jackson.databind.ObjectMapper;
// import org.junit.jupiter.api.Test;
// import org.springframework.beans.factory.annotation.Autowired;
// import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
// import org.springframework.boot.test.context.SpringBootTest;
// import org.springframework.http.MediaType;
// import org.springframework.test.web.servlet.MockMvc;
// import org.springframework.transaction.annotation.Transactional;

// import java.util.Map;

// import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
// import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
// import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
// import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
// import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
// import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// @SpringBootTest
// @AutoConfigureMockMvc
// @Transactional
// class BookApiTest {

//     @Autowired
//     private MockMvc mockMvc;

//     @Autowired
//     private ObjectMapper objectMapper;

//     private String bookJson(String title, String author, String isbn, Integer stock) throws Exception {
//         if (stock == null) {
//             return objectMapper.writeValueAsString(Map.of("title", title, "author", author, "isbn", isbn));
//         }
//         return objectMapper.writeValueAsString(
//             Map.of("title", title, "author", author, "isbn", isbn, "stock", stock));
//     }

//     private long createBook(String title, String author, String isbn, Integer stock) throws Exception {
//         String body = mockMvc.perform(post("/api/books")
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(bookJson(title, author, isbn, stock)))
//             .andExpect(status().isCreated())
//             .andExpect(header().exists("Location"))
//             .andReturn()
//             .getResponse()
//             .getContentAsString();
//         return objectMapper.readTree(body).get("id").asLong();
//     }

//     @Test
//     void healthReturnsOk() throws Exception {
//         mockMvc.perform(get("/health"))
//             .andExpect(status().isOk())
//             .andExpect(jsonPath("$.status").value("ok"));
//     }

//     @Test
//     void createThenGetAndList() throws Exception {
//         long id = createBook("深入理解计算机系统", "Randal E. Bryant", "9787111544937", 5);

//         mockMvc.perform(get("/api/books/{id}", id))
//             .andExpect(status().isOk())
//             .andExpect(jsonPath("$.id").value((int) id))
//             .andExpect(jsonPath("$.title").value("深入理解计算机系统"))
//             .andExpect(jsonPath("$.author").value("Randal E. Bryant"))
//             .andExpect(jsonPath("$.isbn").value("9787111544937"))
//             .andExpect(jsonPath("$.stock").value(5));

//         mockMvc.perform(get("/api/books").param("keyword", "计算机"))
//             .andExpect(status().isOk())
//             .andExpect(jsonPath("$[0].id").value((int) id));
//     }

//     @Test
//     void duplicateIsbnReturnsConflict() throws Exception {
//         String body = bookJson("A", "B", "ISBN-DUP-1", 1);
//         mockMvc.perform(post("/api/books")
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(body))
//             .andExpect(status().isCreated());

//         mockMvc.perform(post("/api/books")
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(body))
//             .andExpect(status().isConflict())
//             .andExpect(jsonPath("$.code").value("ISBN_ALREADY_EXISTS"));
//     }

//     @Test
//     void updateStockAndValidation() throws Exception {
//         long id = createBook("C", "D", "ISBN-STOCK-1", 2);

//         mockMvc.perform(patch("/api/books/{id}/stock", id)
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(objectMapper.writeValueAsString(Map.of("stock", 8))))
//             .andExpect(status().isOk())
//             .andExpect(jsonPath("$.stock").value(8));

//         mockMvc.perform(patch("/api/books/{id}/stock", id)
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(objectMapper.writeValueAsString(Map.of("stock", -1))))
//             .andExpect(status().isBadRequest())
//             .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));

//         mockMvc.perform(patch("/api/books/{id}/stock", 999999)
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(objectMapper.writeValueAsString(Map.of("stock", 1))))
//             .andExpect(status().isNotFound())
//             .andExpect(jsonPath("$.code").value("BOOK_NOT_FOUND"));
//     }

//     @Test
//     void missingBookReturnsNotFound() throws Exception {
//         mockMvc.perform(get("/api/books/{id}", 999999))
//             .andExpect(status().isNotFound())
//             .andExpect(jsonPath("$.code").value("BOOK_NOT_FOUND"));
//     }

//     @Test
//     void invalidCreateReturnsValidationError() throws Exception {
//         String body = objectMapper.writeValueAsString(
//             Map.of("title", "", "author", "", "isbn", "", "stock", -2));
//         mockMvc.perform(post("/api/books")
//                 .contentType(MediaType.APPLICATION_JSON)
//                 .content(body))
//             .andExpect(status().isBadRequest())
//             .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
//     }
// }

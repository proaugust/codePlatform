package main

import (
	"context"
	"log"
	"net/http"
	"os"

	"example.com/autocode/internal/handler"
	"example.com/autocode/internal/repository"
	"example.com/autocode/internal/service"
)

func main() {
	ctx := context.Background()
	repo, err := repository.NewBookRepository(ctx, os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatalf("connect database: %v", err)
	}
	defer repo.Close()

	svc := service.NewBookService(repo)
	bookHandler := handler.NewBookHandler(svc)

	mux := http.NewServeMux()
	bookHandler.Register(mux)

	addr := "127.0.0.1:8072"
	log.Printf("listening on http://%s", addr)
	if err := http.ListenAndServe(addr, handler.CORS(mux)); err != nil {
		log.Fatal(err)
	}
}

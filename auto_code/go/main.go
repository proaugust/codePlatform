package main

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
)

type Book struct {
	ID     int64  `json:"id"`
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type createBookRequest struct {
	Title  string `json:"title"`
	Author string `json:"author"`
	Stock  int    `json:"stock"`
}

type stockRequest struct {
	Delta *int `json:"delta"`
}

type errorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type errorEnvelope struct {
	Error errorBody `json:"error"`
}

type dataEnvelope struct {
	Data interface{} `json:"data"`
}

type apiError struct {
	status  int
	code    string
	message string
}

func (e *apiError) Error() string { return e.message }

var (
	errInvalidArgument = &apiError{http.StatusBadRequest, "INVALID_ARGUMENT", "请求参数非法"}
	errInvalidID       = &apiError{http.StatusBadRequest, "INVALID_ID", "图书 ID 非法"}
	errNotFound        = &apiError{http.StatusNotFound, "NOT_FOUND", "图书不存在"}
	errInternal        = &apiError{http.StatusInternalServerError, "INTERNAL_ERROR", "服务内部错误"}
)

type Store struct {
	mu     sync.RWMutex
	books  map[int64]*Book
	nextID int64
}

func NewStore() *Store {
	return &Store{books: make(map[int64]*Book), nextID: 1}
}

func (s *Store) List() []*Book {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*Book, 0, len(s.books))
	for _, b := range s.books {
		cp := *b
		out = append(out, &cp)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

func (s *Store) Get(id int64) (*Book, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	b, ok := s.books[id]
	if !ok {
		return nil, errNotFound
	}
	cp := *b
	return &cp, nil
}

func (s *Store) Create(req createBookRequest) (*Book, error) {
	title := strings.TrimSpace(req.Title)
	author := strings.TrimSpace(req.Author)
	if title == "" || author == "" || req.Stock < 0 {
		return nil, errInvalidArgument
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	b := &Book{ID: s.nextID, Title: title, Author: author, Stock: req.Stock}
	s.nextID++
	s.books[b.ID] = b
	cp := *b
	return &cp, nil
}

func (s *Store) UpdateStock(id int64, delta int) (*Book, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	b, ok := s.books[id]
	if !ok {
		return nil, errNotFound
	}
	if b.Stock+delta < 0 {
		return nil, errInvalidArgument
	}
	b.Stock += delta
	cp := *b
	return &cp, nil
}

func (s *Store) Delete(id int64) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.books[id]; !ok {
		return errNotFound
	}
	delete(s.books, id)
	return nil
}

type Server struct {
	store *Store
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

func writeError(w http.ResponseWriter, err error) {
	ae := errInternal
	var target *apiError
	if errors.As(err, &target) {
		ae = target
	}
	writeJSON(w, ae.status, errorEnvelope{Error: errorBody{Code: ae.code, Message: ae.message}})
}

func decodeBody(w http.ResponseWriter, r *http.Request, dst interface{}) error {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(dst); err != nil {
		return errInvalidArgument
	}
	return nil
}

func parseID(r *http.Request) (int64, error) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		return 0, errInvalidID
	}
	return id, nil
}

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) listBooks(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, dataEnvelope{Data: s.store.List()})
}

func (s *Server) getBook(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	b, err := s.store.Get(id)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, dataEnvelope{Data: b})
}

func (s *Server) createBook(w http.ResponseWriter, r *http.Request) {
	var req createBookRequest
	if err := decodeBody(w, r, &req); err != nil {
		writeError(w, err)
		return
	}
	b, err := s.store.Create(req)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, dataEnvelope{Data: b})
}

func (s *Server) updateStock(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	var req stockRequest
	if err := decodeBody(w, r, &req); err != nil {
		writeError(w, err)
		return
	}
	if req.Delta == nil {
		writeError(w, errInvalidArgument)
		return
	}
	b, err := s.store.UpdateStock(id, *req.Delta)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, dataEnvelope{Data: b})
}

func (s *Server) deleteBook(w http.ResponseWriter, r *http.Request) {
	id, err := parseID(r)
	if err != nil {
		writeError(w, err)
		return
	}
	if err := s.store.Delete(id); err != nil {
		writeError(w, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

var allowedOrigins = map[string]bool{
	"http://localhost:5173": true,
	"http://localhost:5174": true,
	"http://localhost:5175": true,
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if allowedOrigins[origin] {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

const indexHTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>图书管理</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#f5f6f8;color:#222}
h1{font-size:20px}
table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1)}
th,td{padding:10px 12px;border-bottom:1px solid #eee;text-align:left}
th{background:#fafafa;font-weight:600}
button{cursor:pointer;border:none;border-radius:4px;padding:6px 12px;background:#e53935;color:#fff}
button:hover{background:#c62828}
#msg{margin:12px 0;min-height:20px;color:#c62828}
#empty{color:#888;padding:16px}
</style>
</head>
<body>
<h1>图书列表</h1>
<div id="msg"></div>
<table>
<thead><tr><th>ID</th><th>标题</th><th>作者</th><th>库存</th><th>操作</th></tr></thead>
<tbody id="rows"></tbody>
</table>
<div id="empty" style="display:none">暂无图书</div>
<script>
const rows=document.getElementById('rows');
const msg=document.getElementById('msg');
const empty=document.getElementById('empty');
function setMsg(t){msg.textContent=t||'';}
async function load(){
  setMsg('');
  try{
    const res=await fetch('/api/books');
    const body=await res.json();
    const list=(body&&body.data)||[];
    rows.innerHTML='';
    empty.style.display=list.length?'none':'block';
    for(const b of list){
      const tr=document.createElement('tr');
      tr.innerHTML='<td>'+b.id+'</td><td></td><td></td><td>'+b.stock+'</td><td></td>';
      tr.children[1].textContent=b.title;
      tr.children[2].textContent=b.author;
      const btn=document.createElement('button');
      btn.textContent='删除';
      btn.onclick=()=>remove(b);
      tr.children[4].appendChild(btn);
      rows.appendChild(tr);
    }
  }catch(e){setMsg('加载失败：'+e);}
}
async function remove(b){
  if(!confirm('确定删除《'+b.title+'》吗？'))return;
  try{
    const res=await fetch('/api/books/'+b.id,{method:'DELETE'});
    if(res.status===204){await load();return;}
    let m='删除失败';
    try{const eb=await res.json();if(eb&&eb.error)m=eb.error.code+': '+eb.error.message;}catch(_){}
    setMsg(m);
  }catch(e){setMsg('删除失败：'+e);}
}
load();
</script>
</body>
</html>`

func (s *Server) index(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(indexHTML))
}

func main() {
	srv := &Server{store: NewStore()}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", srv.health)
	mux.HandleFunc("GET /{$}", srv.index)
	mux.HandleFunc("GET /api/books", srv.listBooks)
	mux.HandleFunc("POST /api/books", srv.createBook)
	mux.HandleFunc("GET /api/books/{id}", srv.getBook)
	mux.HandleFunc("DELETE /api/books/{id}", srv.deleteBook)
	mux.HandleFunc("PATCH /api/books/{id}/stock", srv.updateStock)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8072"
	}
	addr := ":" + port
	log.Printf("listening on %s", addr)
	if err := http.ListenAndServe(addr, withCORS(mux)); err != nil {
		log.Fatal(err)
	}
}

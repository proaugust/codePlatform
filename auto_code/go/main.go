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
	ID     *int64 `json:"id"`
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
	errInvalidArgument = &apiError{http.StatusBadRequest, "VALIDATION_ERROR", "请求参数非法"}
	errInvalidID       = &apiError{http.StatusBadRequest, "VALIDATION_ERROR", "图书 id 必须为大于 0 的整数"}
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
	if req.ID != nil && *req.ID <= 0 {
		return nil, errInvalidID
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
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"code":    "OK",
		"message": "deleted",
		"data":    map[string]int64{"id": id},
	})
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
body{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#f7f7f8;color:#222}
h1{font-size:20px;margin:0 0 16px}
table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08)}
th,td{padding:10px 12px;border-bottom:1px solid #eee;text-align:left;font-size:14px}
th{background:#fafafa;font-weight:600}
tr.selected{background:#eef5ff}
button{cursor:pointer;border:1px solid #ccc;background:#fff;border-radius:6px;padding:6px 12px;font-size:13px}
button.primary{background:#2563eb;border-color:#2563eb;color:#fff}
button.danger{background:#dc2626;border-color:#dc2626;color:#fff}
button:disabled{opacity:.5;cursor:not-allowed}
.toolbar{display:flex;gap:8px;margin-bottom:12px;align-items:center}
#msg{margin-left:8px;font-size:13px}
#msg.err{color:#dc2626}
#msg.ok{color:#16a34a}
.form{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.form input{padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:13px}
</style>
</head>
<body>
<h1>图书管理</h1>
<div class="form">
<input id="title" placeholder="书名">
<input id="author" placeholder="作者">
<input id="stock" type="number" placeholder="库存" value="0" style="width:90px">
<button class="primary" id="addBtn">新增</button>
</div>
<div class="toolbar">
<button class="danger" id="delBtn" disabled>删除选中</button>
<span id="msg"></span>
</div>
<table>
<thead><tr><th></th><th>ID</th><th>书名</th><th>作者</th><th>库存</th></tr></thead>
<tbody id="rows"></tbody>
</table>
<script>
const rows=document.getElementById('rows');
const delBtn=document.getElementById('delBtn');
const msg=document.getElementById('msg');
let selected=null;
function setMsg(t,ok){msg.textContent=t||'';msg.className=ok?'ok':'err';}
async function load(){
  try{
    const r=await fetch('/api/books');
    const j=await r.json();
    const list=(j&&j.data)||[];
    rows.innerHTML='';
    selected=null;delBtn.disabled=true;
    if(!list.length){rows.innerHTML='<tr><td colspan="5" style="color:#888">暂无图书</td></tr>';return;}
    for(const b of list){
      const tr=document.createElement('tr');
      tr.innerHTML='<td><input type="radio" name="sel"></td><td>'+b.id+'</td><td>'+esc(b.title)+'</td><td>'+esc(b.author)+'</td><td>'+b.stock+'</td>';
      tr.querySelector('input').addEventListener('change',()=>{
        rows.querySelectorAll('tr').forEach(x=>x.classList.remove('selected'));
        tr.classList.add('selected');
        selected=b;delBtn.disabled=false;
      });
      rows.appendChild(tr);
    }
  }catch(e){setMsg('加载失败: '+e.message,false);}
}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
delBtn.addEventListener('click',async()=>{
  if(!selected)return;
  if(!confirm('确认删除图书「'+selected.title+'」？'))return;
  try{
    const r=await fetch('/api/books/'+selected.id,{method:'DELETE'});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){
      const m=(j&&j.error&&j.error.message)||('删除失败('+r.status+')');
      setMsg(m,false);return;
    }
    setMsg('删除成功',true);
    await load();
  }catch(e){setMsg('删除失败: '+e.message,false);}
});
document.getElementById('addBtn').addEventListener('click',async()=>{
  const title=document.getElementById('title').value.trim();
  const author=document.getElementById('author').value.trim();
  const stock=parseInt(document.getElementById('stock').value||'0',10);
  try{
    const r=await fetch('/api/books',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,author,stock})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){
      const m=(j&&j.error&&j.error.message)||('新增失败('+r.status+')');
      setMsg(m,false);return;
    }
    setMsg('新增成功',true);
    document.getElementById('title').value='';
    document.getElementById('author').value='';
    document.getElementById('stock').value='0';
    await load();
  }catch(e){setMsg('新增失败: '+e.message,false);}
});
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

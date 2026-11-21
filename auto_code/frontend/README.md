# Auto-generated Vue Frontend

java / go 共用的无登录业务前端，通过 Vite 代理访问当前选中的后端。

目录：`auto_code/frontend`（与 java、go 同级）。

## 启动

- 双击 `run_frontend.bat`，或在本目录执行：

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 5175
```

- 前端: http://127.0.0.1:5175
- 当前代理后端: http://127.0.0.1:8072
- 后端端口: java=8070, go=8072
- 请先启动对应语言后端；控制台「启动前端」会按当前语言改写代理目标。

# Deployment Information

## Public URL

https://day14-agent-c14l.onrender.com

## Platform

Render. Blueprint [`06-lab-complete/render.yaml`](06-lab-complete/render.yaml) khai báo hai tài nguyên dùng gói Free tại Singapore.

| Tài nguyên | Loại | Vai trò |
| --- | --- | --- |
| `day14-agent` | Docker Web Service | Chạy agent Part 6 từ `06-lab-complete/`. |
| `day14-redis` | Key Value, Valkey 8 tương thích Redis | Lưu trạng thái rate limit và budget dùng chung giữa các worker. |

Dashboard ghi nhận Agent `Deployed` và Key Value `Available`, cùng vùng Singapore. Agent ở trạng thái Live với commit `4c32d1b`, truy cập được qua HTTPS. `/ready` trả `200`, xác nhận kết nối Redis hoạt động.

## Test Commands

Thiết lập URL cho phiên kiểm thử.

```bash
BASE='https://day14-agent-c14l.onrender.com'
```

API key được nhập tương tác và ẩn khi nhập, không lưu giá trị trong file lệnh.

```bash
read -r -s -p 'AGENT_API_KEY: ' AGENT_API_KEY
```

Kiểm tra bốn trường hợp HTTP theo CP6.

### Health Check

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Expected: 200
```

### Readiness Check

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Expected: 200
```

### API Test (without authentication)

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
# Expected: 401
```

### API Test (with authentication)

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
# Expected: 200
```

Dọn biến xác thực sau kiểm thử.

```bash
unset AGENT_API_KEY
```

### Test Results

| Phép thử | Kết quả thực tế |
| --- | --- |
| `GET /health` | `200`, `{"status":"ok"}`. |
| `GET /ready` | `200`, `{"ready":true}`. |
| `POST /ask`, thiếu key | `401`, `{"detail":"Missing or invalid API key"}`. |
| `POST /ask`, đúng key | `200`, JSON có `question: "Hello"` và `answer` chứa câu trả lời mock. |

Kiểm thử ngày 26/11/2026 (GMT+7): health, readiness và request thiếu key lúc 19:13; request có key lúc 19:30:28. Phản hồi của request có xác thực:

```http
HTTP/2 200
date: Thu, 26 Nov 2026 12:30:28 GMT
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Kiểm tra sau deploy bằng `python check_production_ready.py --public-url https://day14-agent-c14l.onrender.com` trong `06-lab-complete/` đạt **PASS 12/12**, **44/44 checks passed**, gồm kiểm tra local, Docker và `/health` public.

## Environment Variables Set

Các biến dưới đây được khai báo trong Blueprint. Bảng chỉ ghi cấu hình và cách cấp giá trị, không ghi secret.

| Biến | Cấu hình |
| --- | --- |
| `PORT` | `8000`. Dockerfile truyền giá trị này vào Uvicorn. |
| `ENVIRONMENT` | `production`. |
| `REDIS_URL` | Tham chiếu `connectionString` nội bộ của `day14-redis`. |
| `AGENT_API_KEY` | Nhập trên Render qua `sync: false`. |
| `RATE_LIMIT_PER_MINUTE` | `10`. |
| `DAILY_BUDGET_USD` | `1.0`, dùng cho cost guard giả lập. |

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)

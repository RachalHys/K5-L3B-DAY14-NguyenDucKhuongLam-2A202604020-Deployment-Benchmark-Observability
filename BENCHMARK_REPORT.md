# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Đức Khương Lam (2A202604020)

**Ngày chạy CP7:** 26/11/2026

**Môi trường CP7:** Ubuntu 24.04.4 trên WSL2 x86_64, Intel Core i7-9750H, Python 3.12.3. Agent và client chạy trên cùng máy, dùng `mock-llm-small`.

**Ngày chạy CP8:** 26/11/2026. Chạy stack Docker trên cùng máy WSL2, một worker mỗi Agent.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py` cho thời gian phản hồi của phần lớn request thành công. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`, cao hơn mức lỗi upstream mô phỏng 1% để có dư địa cho dao động lấy mẫu. |
| Accuracy trên golden dataset | ≥ 85% | Ngưỡng quality gate của Exercise 7.3. Lượt nghiệm thu v2 sau khi bổ sung kiến thức dùng ngưỡng 100% và kiểm tra regression. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Mỗi lượt đo gửi 300 request tới v2 ở cổng `8002`, sau một request warm-up. Giữ `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. RPS tính trên toàn bộ request, các percentile latency tính trên phản hồi HTTP `200`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| [1](06-lab-complete/benchmark-observability/develop/reports/load_v2_c1.json) | 4,36 | 192,1 | 219,3 | 1.686,7 | 1,33% | PASS |
| [10](06-lab-complete/benchmark-observability/develop/reports/load_v2_c10.json) | 42,25 | 189,2 | 219,2 | 1.662,1 | 1,00% | PASS |
| [50](06-lab-complete/benchmark-observability/develop/reports/load_v2_c50.json) | 106,92 | 198,3 | 310,7 | 1.708,9 | 1,00% | PASS |
| [100](06-lab-complete/benchmark-observability/develop/reports/load_v2_c100.json) | 47,80 | 973,2 | 4.644,6 | 5.258,0 | 0,67% | FAIL (p95) |

**Nhận xét.** RPS tăng gần tỷ lệ thuận từ concurrency 1 đến 10 vì các tác vụ chờ bất đồng bộ có thể chạy xen kẽ. RPS cao nhất ở concurrency 50. Ở mức 100, RPS giảm còn 47,80 và p95 tăng lên 4.644,6 ms. Client và server chạy chung máy nên phép đo chưa xác định được nút thắt nằm ở phía nào.

### 2.2 Tail latency

Mỗi cấu hình được chạy sau khi khởi động lại v2, với 300 request và concurrency 20. Các tham số mock còn lại giữ mặc định.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| [0](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.json) | 192,1 | 221,2 | 250,1 |
| [0.03 (mặc định)](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.03.json) | 226,5 | 223,8 | 1.674,1 |
| [0.1](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.1.json) | 366,7 | 1.694,8 | 1.713,6 |

**Nhận xét.** Từ tỷ lệ chậm 0 lên 3%, trung bình chỉ tăng 34,4 ms, còn p99 tăng 1.424,0 ms. Một nhóm nhỏ request chậm có ảnh hưởng hạn chế lên trung bình nhưng nằm ngay ở phần đuôi phân bố. Ở mức 10%, p95 cũng vượt SLO, đạt 1.694,8 ms. Dùng p95 để kiểm tra mức phục vụ của phần lớn request và theo dõi p99 để phát hiện nhóm chậm nhất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Agent v1 chạy ở cổng `8001`, v2 ở cổng `8002`. Mỗi lượt dùng 23 câu của golden dataset. Một câu đạt khi câu trả lời chứa ít nhất 60% keyword kỳ vọng. Hai lượt baseline dùng ngưỡng mặc định 80%, lượt sau khi bổ sung kiến thức dùng ngưỡng 100% và lấy v2 ban đầu làm baseline.

| Chỉ số | [Agent v1](06-lab-complete/benchmark-observability/develop/reports/eval_v1.json) | [Agent v2](06-lab-complete/benchmark-observability/develop/reports/eval_v2.json) | [Agent v2 (sau khi sửa KB)](06-lab-complete/benchmark-observability/develop/reports/eval_v2_fixed.json) |
|---|---|---|---|
| Accuracy | 4,35% (1/23) | 91,30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57,4 | 109,0 | 114,8 |
| Tổng cost (USD) | 0,000408 | 0,000760 | 0,000800 |
| Cost / câu đúng (USD) | 0,00040815 | 0,00003619 | 0,00003479 |
| Quality gate | FAIL (80%) | PASS (80%, 0 regression) | PASS (100%, 0 regression) |

**Phân tích hai câu v2 chưa đạt.**

| ID | Keyword bị thiếu | Bổ sung trong `KNOWLEDGE_BASE` |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Phân biệt API key với JWT và mô tả cách xác minh chữ ký, kiểm tra thời hạn token. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Mô tả cách Kubernetes HPA điều chỉnh số pod dựa trên CPU, bộ nhớ hoặc custom metrics. |

**Đánh đổi chất lượng, chi phí và độ trễ.** V2 truy xuất tài liệu để trả lời chính xác hơn. Bước truy xuất thêm thời gian xử lý và kéo dài prompt, làm tăng số token và tổng chi phí mô phỏng. Chi phí trên mỗi câu đúng giảm từ 0,00040815 USD ở v1 còn 0,00003479 USD ở v2 sau khi sửa vì chi phí được chia cho nhiều câu đạt hơn. Dùng số liệu load test để đánh giá đuôi độ trễ vì tập eval 23 câu dễ bị chi phối bởi một vài phản hồi chậm ngẫu nhiên.

**Quality gate trong CI.** Job khởi động phiên bản cần đánh giá, đợi `/health` trả `200` rồi chạy eval từ `develop/`. `BASELINE_JSON` trỏ tới báo cáo eval đã được chấp nhận trên nhánh đích.

```bash
python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.85 --baseline "$BASELINE_JSON"
```

Script trả `0` khi accuracy đạt ít nhất 85% và không có câu từ đúng chuyển thành sai. Nếu một trong hai điều kiện không đạt, script trả `1` và job thất bại. Khi job được đặt làm kiểm tra bắt buộc, kết quả thất bại sẽ chặn merge. [Script eval](06-lab-complete/benchmark-observability/develop/eval/run_eval.py)

---

## 4. Observability stack (production)

Stack CP8 chạy bằng Docker Compose với project `k5-day14-observability`. Locust gửi request qua Nginx, Prometheus scrape từng Agent và Grafana hiển thị số liệu. Jaeger nhận trace qua OTLP/HTTP. Dockerfile đặt home của user `agent` tại `/home/agent` để Python nạp thư viện từ đúng thư mục `.local` đã được copy từ stage build.

### 4.1 Screenshot

- [x] [Grafana khi Locust đang tạo tải](screenshots/grafana-dashboard.png)
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [x] [Trace lỗi và event `exception` trong Jaeger](screenshots/jaeger-error-trace.png)
- [x] [Hai alert cùng firing trên Prometheus](screenshots/prometheus-alert-firing.png)

**Kết quả Exercise 7.4.** Với 30 user, tăng 5 user/giây và 2 replica, ảnh Grafana ghi nhận `/ask` đạt 19,1 req/s, tỷ lệ `5xx` là 1,27%, p95 là 291,81 ms và 1 request đang xử lý. Truy vấn Prometheus ở cuối khoảng thời gian trong ảnh cho latency trung bình khoảng 225 ms. p95 cao hơn trung bình khoảng 67 ms, phản ánh nhóm phản hồi chậm hơn mức điển hình.

- Hai Agent nhận khoảng 9,56 và 9,55 req/s, cho thấy Nginx chia tải gần đều trong khoảng đo.
- Số token đầu vào khoảng 1.400 token/s, cao hơn 743 token/s đầu ra theo giá trị từng series. Prompt chứa system prompt, câu hỏi và tài liệu truy xuất, trong khi đầu ra chỉ gồm câu trả lời. Panel `Tokens/s` vẽ chồng hai series.
- `GET /metrics` qua Nginx trả `404` theo cấu hình. Prometheus scrape trực tiếp từng Agent trong mạng Docker để không công khai metrics qua cổng API.

### 4.2 Thí nghiệm "phá hệ thống"

Mỗi lượt chạy với 30 user và 2 replica. Thời gian tính từ lúc bắt đầu áp dụng cấu hình đến lần đầu ghi nhận trạng thái `firing`, với chu kỳ kiểm tra khoảng 2 giây. Bộ kiểm thử rule đi kèm lab chạy bằng `promtool` trả `SUCCESS`.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 95,3 giây | `Error rate` |
| B | `MOCK_SLOW_RATE=0.3`, giữ `MOCK_ERROR_RATE=0.2` | `AgentHighLatencyP95` | 156,5 giây | `Latency p95` |

Ở lượt B, hai rule cùng `firing`. Prometheus ghi nhận tỷ lệ lỗi 18,38%, vượt ngưỡng 5%, và p95 khoảng 1,90 giây, vượt ngưỡng 1 giây. Rule lỗi yêu cầu điều kiện kéo dài 1 phút, còn rule độ trễ yêu cầu 2 phút. Thời gian đo gồm cả thời gian tạo lại Agent và thu mẫu sau khi tăng tải.

**Phát hiện suy giảm chất lượng.** Đổi sang v1 có thể làm accuracy giảm dù request vẫn trả `200` và các ngưỡng lỗi, độ trễ vẫn đạt. Chạy eval định kỳ trên bộ câu hỏi chuẩn và theo dõi accuracy theo phiên bản. Trước khi deploy, dùng quality gate để chặn bản dưới ngưỡng hoặc có regression.

### 4.3 Debug bằng trace

**Trace chậm.** `cfe0ad726ba88a4a04c37e747a7d4036` là trace `POST /ask` dài nhất trong nhóm kết quả Jaeger đã xem ở lượt tải 1 replica. Tổng thời gian là 2.170,46 ms. Trong các bước xử lý của Agent, `chat mock-llm-small` mất 1.672,90 ms, chiếm 77,08% tổng thời gian. Span truy xuất mất 107,49 ms. Log `llm_call` có cùng `trace_id` và ghi thời gian mock LLM là 1.671,6 ms.

```json
{"ts":"2026-11-26T16:36:32.772719+00:00","level":"INFO","service":"observable-agent","instance":"0777a7cfbd07","event":"llm_call","trace_id":"cfe0ad726ba88a4a04c37e747a7d4036","span_id":"fe886e5c1dba7c4d","request_id":"2d4e8c56755a","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":4.7e-05,"llm_ms":1671.6}
```

**Trace lỗi.** `26398da982e0d1646e313482318338b0` trả HTTP `503`. Span `chat mock-llm-small` có event `exception` kiểu `utils.mock_llm.LLMError` do lỗi upstream mô phỏng. Log `llm_error` khớp `trace_id`.

```json
{"ts":"2026-11-26T16:37:55.417044+00:00","level":"INFO","service":"observable-agent","instance":"50c667344281","event":"llm_error","trace_id":"26398da982e0d1646e313482318338b0","span_id":"f0b08ac0da5f54b8","request_id":"2012ccd96041","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Hai lượt chạy trong 2 phút với 100 user, tăng 10 user/giây. Cả hai dùng v2, `mock-llm-small`, độ trễ cơ sở 120 ms, tỷ lệ chậm 3% và tỷ lệ lỗi 1%. Bảng lấy dòng `Aggregated` trong CSV của Locust, gồm cả `/ask` và `/health`.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| [1](benchmark-results/scale_1_stats.csv) | 63,52 | 210 | 980 | 1.800 | 63/7.402 (0,85%) |
| [3](benchmark-results/scale_3_stats.csv) | 66,94 | 190 | 230 | 1.700 | 75/7.847 (0,96%) |

**Nhận xét.** Tăng từ 1 lên 3 replica giảm p95 từ 980 ms xuống 230 ms. Riêng `/ask`, p95 giảm từ 1.100 ms xuống 230 ms, phù hợp với việc chia tải giữa các Agent. RPS tăng từ 63,52 lên 66,94 ở mức tải cố định này. Locust có 100 user và mỗi user nghỉ 0,5–2 giây giữa các tác vụ, nên phép đo chỉ cho biết throughput ứng với cấu hình tải đã chạy. p99 vẫn khoảng 1,7 giây. Trong trace chậm đã đối chiếu, lời gọi mock LLM chiếm phần lớn thời gian xử lý.

---

## 6. Kết luận

1. p95 và p99 cho thấy những phản hồi chậm dễ bị che lấp khi chỉ nhìn trung bình.
2. Metrics chỉ ra thời điểm có vấn đề. Trace và log cùng `trace_id` giúp tìm bước xử lý gây chậm hoặc lỗi.
3. Accuracy cần được đo bằng eval. Một phiên bản có thể trả `200` đều đặn nhưng cho câu trả lời kém hơn.

Trong production, cần theo dõi thêm tỷ lệ `5xx` và độ trễ ở Nginx để phát hiện lỗi từ góc nhìn client, đồng thời đặt cảnh báo chất lượng dựa trên eval định kỳ.

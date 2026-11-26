# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Đức Khương Lam (2A202604020)

**Ngày chạy CP7:** 26/11/2026

**Môi trường CP7:** Ubuntu 24.04.4 trên WSL2 x86_64, Intel Core i7-9750H, Python 3.12.3. Agent và client chạy trên cùng máy, dùng `mock-llm-small`.

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

Phần 4–6 được điền ở CP8 sau khi có kết quả đo trên stack Docker.

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 2 alert cùng **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...

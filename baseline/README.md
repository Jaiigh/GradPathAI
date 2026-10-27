# GradPath baseline + benchmark (สำหรับสไลด์ 11 และ 16)

ใช้เวลารันรวมประมาณ 15–20 นาทีบนเครื่องที่มี GPU และ Ollama

## 0. เตรียมเครื่อง
```bash
ollama pull qwen3:4b
ollama pull qwen3:8b
pip install ortools          # dependency เดียว ส่วนที่เหลือเป็น standard library
python agent.py --mock       # ทดสอบแบบ offline ต้องจบที่ "final_state": "DONE"
```

## 1. Benchmark → สไลด์ 11 (Chayaphon)
```bash
python bench.py
```
- ใช้ protocol ของ W9: warm-up 1 รอบ แล้ววัด 3 รอบ, temperature 0, num_ctx 8192, num_predict 256 และ unload model ระหว่างแต่ละ model
- ผลอยู่ใน `results/bench_summary.md` (ตาราง) และ `results/bench_runs.csv` (ค่าดิบ)
- ช่อง **GPU fit** ให้ใช้บรรทัดท้ายสุดของ `bench_summary.md` เช่น `100% GPU, 5.9 GB @ ctx 8192, 72 tok/s`
  ถ้าค่าต่ำกว่า 100% แปลว่า model ล้นไปใช้ CPU (offload cliff) ต้องพูดถึงตอน pitch

## 2. Baseline end-to-end → สไลด์ 16 และ Progress update (Techit)
```bash
python agent.py --model qwen3:8b
python agent.py --model qwen3:4b
```
ลำดับการทำงานของ agent:
`VERIFY_INPUT → CLARIFY → ACT (LLM เรียก audit → retrieve_courses → solve_plan [CP-SAT]) → submit_final → FINAL_GATE (validate_plan) → DONE`
- case ที่ใช้คือ `data/case_ai_cap3.json` ซึ่งเป็นตัวอย่างเดียวกับสไลด์ 10 (C101 และ G101 ผ่านแล้ว, cap 3 หน่วยกิตต่อเทอม, เน้น AI) คำตอบที่คาดไว้คือ T1: C102, T2: E202
- ผลสรุปแต่ละรันจะต่อท้ายไว้ใน `results/baseline_results.csv` ส่วน trace ทุกขั้นอยู่ใน `traces/*.jsonl` ใช้โชว์ตอน progress update ได้เลย
- ใช้ `python show_trace.py` เพื่อดู trace ล่าสุดแบบอ่านง่าย
- budget เป็นค่าเดียวกับสไลด์ 6: tool calls ≤ 8, revisions ≤ 2, เวลา ≤ 120 s

## 3. เอาตัวเลขไปใส่สไลด์ 11
| ช่อง | เอามาจาก |
|---|---|
| Task accuracy | ยังไม่มี task set 20 ข้อ ให้เขียน `Smoke 1/1 DONE (20-task set pending)` หรือ 0/1 ตามผลจริง |
| Case latency | ค่า `e2e_s` ใน `baseline_results.csv` ของแต่ละ model |
| GPU fit | บรรทัด "Slide 11" ใน `bench_summary.md` |

## 4. ข้อความสำหรับสไลด์ 16 (หลังรันผ่านแล้ว)
- **Existing evidence:** `Baseline runs end to end on qwen3:8b and qwen3:4b: audit → retrieval → CP-SAT → final gate → DONE (trace + timings logged); 25 earlier code/protocol tests`
- **Next implementation:** `Verify PDF data, add CLARIFY/consent dialogue, move loop into Harness M8/M9, build the 20-task set`

ให้ลบคำว่า "obtain Harness" ออก เพราะ Harness.zip มีอยู่ใน Discord แล้ว

## สิ่งที่ baseline นี้ยังไม่มี (บอกตรง ๆ ตอนถูกถาม)
- ข้อมูลเป็นแบบสังเคราะห์ (`data/rules_snapshot.json`) ยังไม่ใช่หลักสูตร CP 2566 จริง
- รับ transcript เป็น CSV ส่วน PDF ingestion เป็นงานถัดไปของ Tanaphan
- retrieval เป็นแบบ keyword ยังไม่ใช่ M15 embeddings
- ยังไม่โต้ตอบกับผู้ใช้ (WAIT_USER จะคืนค่าเป็น NEED_INFO)
- ลูปของ agent ยังเขียนเอง ไม่ได้ใช้ agent loop ของ Harness.zip โดยตรง ส่วน tools (`tools.py`) เป็นฟังก์ชันธรรมดาพร้อม JSON schema ใน `TOOL_SCHEMAS` จึงย้ายไปลงทะเบียนใน M6 tool registry ได้ตรง ๆ

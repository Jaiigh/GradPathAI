# GradPath baseline + benchmark

โค้ดชุดนี้คือ baseline ที่ใช้เป็นหลักฐานในสไลด์ 11, 16 และ 17 ของ pitch v9 (รันเมื่อ 28 ต.ค. 2026 บน RTX 5070 12 GB)
ตัวเลขที่วัดได้และข้อควรระวังในการตีความอยู่ใน [`results/slide_ready.md`](results/slide_ready.md)

## 0. เตรียมเครื่อง
```bash
pip install -r requirements.txt   # ortools เป็น dependency เดียว ที่เหลือเป็น standard library
python agent.py --mock            # ทดสอบแบบ offline ต้องจบที่ "final_state": "DONE"
ollama pull qwen3:8b              # ใช้เมื่อจะรันกับโมเดลจริง
ollama pull qwen3:4b
```
- ทดสอบ `--mock` ซ้ำบน Python 3.13.5 + OR-Tools 9.15.6755 แล้วผ่าน และได้ plan hash เดิม (2 พ.ย. 2026)
- `agent.py` (รวมถึง `--mock`) จะต่อท้ายผลใน `results/baseline_results.csv` และสร้าง trace ใหม่ใน `traces/` ทุกครั้ง ถ้าไม่ต้องการให้ไฟล์ที่ commit แล้วเปลี่ยน ให้ restore ก่อน commit

## 1. Benchmark (สไลด์ 11)
```bash
python bench.py
```
- ใช้ protocol ของ W9: warm-up 1 รอบ แล้ววัด 3 รอบ, temperature 0, seed 42, num_ctx 8192, num_predict 256 และ unload model ระหว่างแต่ละ model
- ผลอยู่ใน `results/bench_summary.md` (ตาราง) และ `results/bench_runs.csv` (ค่าดิบ)
- ถ้า GPU fit ต่ำกว่า 100% แปลว่า model ล้นไปใช้ CPU (offload cliff)

## 2. Baseline end-to-end (สไลด์ 16–17)
```bash
python agent.py --model qwen3:8b
python agent.py --model qwen3:4b
python show_trace.py              # ดู trace ล่าสุดแบบอ่านง่าย
```
ลำดับการทำงานของ agent:
`VERIFY_INPUT → CLARIFY → ACT (LLM เรียก audit → retrieve_courses → solve_plan [CP-SAT]) → submit_final → FINAL_GATE (validate_plan) → DONE`
- case คือ `data/case_ai_cap3.json` ซึ่งเป็นตัวอย่างเดียวกับสไลด์ 10 (C101 และ G101 ผ่านแล้ว, cap 3 หน่วยกิตต่อเทอม, เน้น AI) คำตอบที่คาดไว้คือ T1: C102, T2: E202
- ผลสรุปของแต่ละรันต่อท้ายใน `results/baseline_results.csv` ส่วน trace ทุกขั้นอยู่ใน `traces/*.jsonl`
- budget เท่ากับสไลด์ 6: tool calls ≤ 8, revisions ≤ 2, เวลา ≤ 120 s

## 3. ผลที่ใช้ใน pitch v9
| Profile | ผล | End-to-end | LLM / tool calls | GPU fit |
|---|---|---|---|---|
| qwen3:8b | DONE ตรงคำตอบ | 19.9 s | 4 / 3 | 100% GPU, 6.31 GB, 100.6 tok/s |
| qwen3:4b | DONE ตรงคำตอบ | 32.2 s | 4 / 2 (ข้าม audit) | 100% GPU, 3.88 GB, 154.0 tok/s |
| mock | DONE ตรงคำตอบ | 1.69 s | 5 / 3, revision 1 | - |

ข้อควรระวัง (รายละเอียดอยู่ใน `results/slide_ready.md`):
- qwen3:4b ยังคิดแบบ reasoning อยู่ แม้จะส่ง `think: false` ไปแล้ว turn แรกจึงใช้ token จนครบ 1200 โดยไม่ได้เรียก tool ทำให้เทียบเวลากับ 8B ภายใต้ setting เดียวกันไม่ได้
- เวลา 19.9 s ของ 8B รวมเวลาโหลดโมเดลครั้งแรก 6.4 s และการเรียก LLM แต่ละครั้งยังมีเวลาราว 2 s ที่เกิดนอก Ollama สาเหตุที่น่าจะเป็นคือ `localhost` บน Windows resolve เป็น `::1` ก่อน แล้วรอราว 2 s จึง fallback ไป `127.0.0.1` (ทดลองซ้ำบนเครื่อง dev แล้ว แต่ยังไม่ได้ทดสอบบนเครื่อง benchmark และโค้ดยังใช้ `localhost` อยู่)

## สิ่งที่ baseline นี้ยังไม่มี
- ข้อมูลเป็นแบบสังเคราะห์ (`data/rules_snapshot.json`) ยังไม่ใช่หลักสูตร CP 2566 จริง
- รับ transcript เป็น CSV ยังไม่มี PDF ingestion
- วางแผนได้แค่ 2 เทอม และบังคับให้วิชา required ทุกตัวลงครบภายใน horizon ขณะที่ขอบเขตใหม่หลัง pitch v9 ต้องวางแผนไปจนจบปี 4 (สูงสุด 8 เทอม)
- retrieval เป็นแบบ keyword ยังไม่มี embeddings
- ยังโต้ตอบกับผู้ใช้ไม่ได้ (WAIT_USER จะคืนค่าเป็น NEED_INFO)
- ลูปของ agent เขียนขึ้นเอง (Harness.zip เป็นเพียงตัวอย่าง ไม่จำเป็นต้องใช้) ส่วน tools (`tools.py`) เป็นฟังก์ชันธรรมดาพร้อม JSON schema ใน `TOOL_SCHEMAS`
- ไม่ได้บันทึก model digest และ Ollama version ไว้ในแต่ละรันของ `agent.py`
- ยังไม่มี automated tests (ลบข้อความ "25 earlier code/protocol tests" ออกจาก README ฉบับก่อนแล้ว เพราะใน repo ไม่มีไฟล์ test จริง)
- React UI ยังไม่ได้เชื่อมกับ agent

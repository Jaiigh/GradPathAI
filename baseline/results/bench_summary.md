Ollama 0.40.11 | NVIDIA GeForce RTX 5070, 12227 MiB | num_ctx 8192 | num_predict 256 | temp 0 | 1 warm-up + 3 runs (mean)

| Model | Gen tok/s | Prompt tok/s | TTFT (s) | Loaded / in VRAM | GPU fit | Peak VRAM |
|---|---|---|---|---|---|---|
| qwen3:4b | 154.0 | 8267.7 | 2.09 | 3.88 / 3.88 GB | 100% GPU | 5618 MiB |
| qwen3:8b | 100.6 | 7165.4 | 2.1 | 6.31 / 6.31 GB | 100% GPU | 7756 MiB |

Slide 11 'GPU fit' cell:
- qwen3:4b: 100% GPU, 3.88 GB @ ctx 8192, 154.0 tok/s
- qwen3:8b: 100% GPU, 6.31 GB @ ctx 8192, 100.6 tok/s
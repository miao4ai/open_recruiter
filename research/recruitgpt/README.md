# recruitgpt-research

Data generation, QLoRA training, and RecruitBench evaluation for **RecruitGPT** — a
recruiting-specialised ranking model built by adapting Qwen3-8B.

**[PLAN.md](PLAN.md) is the specification.** It sets out the phases, what has to be true
before each one starts, where the data comes from, and which decisions differ from the
original proposal and why.

## What is here

```
recruitgpt_research/
├── config.py           run configuration, and the guards for multi-GPU QLoRA
├── splits.py           grouped splitting, so synthetic data cannot leak
├── runs.py             one directory per run: config, manifest, environment, metrics
├── data/
│   ├── synthetic.py    deterministic generator — templates, difficulty bands, hard negatives
│   ├── chat.py         example -> chat messages
│   ├── io.py           JSONL, with content fingerprints
│   └── generate.py     CLI
├── train/
│   ├── collate.py      tokenising, and masking everything but the answer
│   └── sft.py          QLoRA entry point, single or multi-GPU
└── evaluation/
    ├── metrics.py      pairwise accuracy, NDCG, MRR, recall
    └── run.py          CLI — writes metrics, predictions, and error analysis
```

The schemas and the prompt format live in the [`recruitgpt`](../../sdk/recruitgpt/) package
instead of here, because training and serving have to build byte-identical prompts. A model
trained against one rendering and served another fails in a way that looks like a bad model.

## Run it on a laptop

Nothing below needs a GPU, an API key, or a network connection after the first model download.

```bash
cd research/recruitgpt
uv sync

# generate a small dataset and split it
uv run python -m recruitgpt_research.data.generate --config configs/debug.yaml --count 80

# what a term-overlap scorer achieves — the floor any model must clear
uv run python -m recruitgpt_research.evaluation.run --config configs/debug.yaml --baseline keyword
```

```json
{
  "baseline": "keyword",
  "pairwise_accuracy": 0.667,
  "hard_pairwise_accuracy": 0.333,
  "mrr": 0.5
}
```

That gap is the point. Overall the keyword baseline looks reasonable; on the pairs involving a
hard negative — full keyword coverage, no depth, a long record — it is wrong two times in
three. A benchmark a term counter can pass is not measuring ranking, which is why
`hard_pairwise_accuracy` is the headline and not the average.

`--baseline oracle` scores 1.0 by construction. If it ever does not, the harness is broken
rather than the model.

## Training

```bash
uv sync --extra train

# CPU, a 0.6B model, about fifteen seconds. The adapter is worthless; the
# pipeline it exercises is the same one a GPU run takes.
uv run python -m recruitgpt_research.train.sft --config configs/debug.yaml

# one GPU
uv run python -m recruitgpt_research.train.sft --config configs/qwen3_8b_qlora.yaml
```

### Several GPUs

```bash
accelerate launch --config_file accelerate/ddp.yaml --num_processes 4 \
    -m recruitgpt_research.train.sft --config configs/qwen3_8b_multi.yaml
```

DDP is the default. A 4-bit 8B base is about 5 GB, so a full copy fits on each GPU and there
is nothing to shard — [`accelerate/fsdp.yaml`](accelerate/) is there for when that stops being
true, not as an upgrade.

Check the plan before the weights download:

```bash
uv run python -m recruitgpt_research.train.sft --config configs/qwen3_8b_multi.yaml --dry-run
```

```
base model        Qwen/Qwen3-8B@main
strategy          ddp
world size        4
effective batch   16
```

**The effective batch is the number to watch.** It is per-device batch × accumulation ×
processes, so going from one GPU to four multiplies it by four unless the accumulation steps
come down. `configs/qwen3_8b_multi.yaml` is written for four processes and lands on 16, the
same as the single-GPU config — the multi-GPU run is meant to reproduce the experiment on more
hardware, not to be a different one.

### Things that fail quietly

Each of these is a guard in `Config.validate`, and each has a test:

| Setting | Wrong value does | 
|---------|------------------|
| `bnb_4bit_quant_storage` ≠ compute dtype under FSDP | A shape error deep in the flat-parameter code, mentioning nothing about quantisation |
| `gradient_checkpointing_use_reentrant: true` with DDP or FSDP | Dies at the first backward pass |
| `ddp_find_unused_parameters: true` with an adapter | Costs a parameter search every step to reach the same answer |
| `fsdp_transformer_layer_cls_to_wrap` naming a class that does not exist | Shards nothing, behaves like slow DDP |
| A distributed strategy launched without `accelerate` | Runs on one GPU and looks entirely normal in the logs |

The last one is recorded rather than rejected: `run_info.json` carries a warning when the
strategy expects several processes and only one is running.

## Reproducibility

Every run writes a directory under `runs/`:

```
runs/recruitgpt-qwen3-8b-ddp-20260823-041500/
├── config.json              every setting, resolved
├── dataset_manifest.json    paths, example counts, content hashes
├── run_info.json            git commit (marked dirty if it was), python, GPUs, world size
├── metrics.json
└── adapter/                 LoRA weights, for pushing to a registry
```

Checkpoints never go into git. The adapter is pushed to a model registry and referenced by
revision; what stays in the repository is enough to explain a run, not to reconstitute it.

## Testing

```bash
uv run pytest          # 53 tests, no GPU
```

Everything that decides whether training would be *correct* — the split, the prompt, the mask,
the metrics, the distributed guards — is tested without hardware. The masking tests run against
the real Qwen3 tokenizer rather than a mock, because the failure they guard against depends on
how that tokenizer merges across the prompt boundary.

Only multi-GPU itself is unverified here: DDP and FSDP are configured, guarded, and dry-run
checked, but no run has been executed on more than one device. That has to happen on real
hardware before the multi-GPU path is trusted.

# RecruitGPT v0.1 — Plan

A domain-specialised recruiting model, trained by adapting an open instruct model rather than
pretraining one. The question it exists to answer:

> Can domain specialisation improve a general model's ability to understand job requirements,
> judge candidate fit, and rank difficult candidates — **beyond what a good prompt already
> achieves**?

The second half of that sentence is the whole experiment. A result that beats a bare base
model but not a well-written prompt is not a result.

---

## Locked decisions

| | Decision | Why |
|--|----------|-----|
| Base model | [`Qwen/Qwen3-8B`](https://huggingface.co/Qwen/Qwen3-8B), Apache 2.0 | 8.2B params, 36 layers, 32k native context, commercially usable |
| Adaptation | QLoRA, configurable rank/alpha | Nothing is hard-coded to one model family |
| Compute | Local for phases 0–2, cloud from phase 3 | The first three phases need no GPU at all |
| Integration | A `Ranker`, not an LLM provider | See below |
| Inference form | **Listwise** reranking over a shortlist | See below |

---

## Where this differs from the original proposal

### 1. It plugs in as a `Ranker`, not as an LLM provider

The proposal sketched `RecruitGPTProvider(LLMProvider)`. There is no `LLMProvider` class in
this repository, and more importantly RecruitGPT's capability is *ranking*, not general chat.
The SDK already has the seam:

```python
class Ranker(Protocol):
    name: str
    def rank(self, job: Job, candidates: list[Candidate], top_k: int = 20) -> list[Match]: ...
```

`LocalSLMRanker` was reserved for exactly this. Plugging in there means the model never has to
pretend to be a general assistant, the existing two-stage architecture applies unchanged, and
the product can switch back per call:

```python
r.ranker = TwoStageRanker(EmbeddingRanker(r.index), RecruitGPTRanker(), shortlist=50)
```

A provider can come later, if and when RecruitGPT-Agent exists. It is not part of v0.1.

### 2. Listwise, not pointwise

The proposal had three inconsistent formulations: a pointwise `match_score` (§5), a listwise
ordering (§6), and pairwise preference training (§17). They have to agree.

Pointwise scoring fails precisely where this work is supposed to win:

```
JD: CUDA Performance Engineer
A: 10 years ML, PyTorch, no CUDA      ← scored alone, this looks strong
B: 4 years, CUDA kernels, Nsight      ← scored alone, this looks junior
```

Judged independently, A wins. **Comparison is the mechanism, not an optimisation.** So the
model reads the job and the whole shortlist together and returns an order with per-candidate
scores and reasons — which is what `rank(job, candidates, top_k)` already asks for.

Pointwise scoring is kept as a baseline, to measure what comparison is worth.

Qwen3-8B's 32k context makes long shortlists technically possible, but candidate profiles are
still compressed: inference cost and latency decide whether this can ship, not whether it fits.

### 3. Baselines before training

The proposal trained in phase 1 and benchmarked later. Reversed. The research question is
about beating a prompt, so the prompt gets measured first — and if a good prompt already
handles the hard cases, that is worth discovering for the price of a few API calls rather
than a training run.

Phase 2 has an explicit stop condition for this reason.

### 4. RecruitHard's independence is a mechanism, not a principle

"Model-independent" was stated but not specified. If the benchmark comes out of the same
pipeline as the training data, a win may only show the model learned the generator. Three
concrete legs:

- **Real job descriptions**, not generated ones — see sourcing below
- **A different model family** generates the benchmark than generated the training data
- **200 human-labelled pairs**, and the agreement between synthetic and human labels is
  reported as a headline number

If that agreement is low, the data pipeline is wrong and no amount of training fixes it.

### 5. RecruitBench and RecruitHard are ordered

The proposal had RecruitBench containing RecruitHard, RecruitHard built from errors mined by
running RecruitBench, and no way in. Untangled:

```
RecruitBench v0   held-out synthetic, exists before any training
      ↓
mine high-confidence errors from RecruitGPT-SFT
      ↓
RecruitHard       real JDs + cross-family generation + human calibration, then frozen
      ↓
RecruitBench v1 = v0 + RecruitHard
```

---

## Data sourcing

Two licensed real sources, used for what only real data can do — and synthetic candidates
everywhere else, because structured ground truth is the methodological backbone.

| Source | Licence | Used for |
|--------|---------|----------|
| [Djinni Recruitment Dataset](https://huggingface.co/datasets/lang-uk/recruitment-dataset-job-descriptions-english) | MIT | Real JDs: distribution statistics that drive synthetic generation, and the JD side of RecruitHard |
| [USAJOBS](https://developer.usajobs.gov/api-reference/) | US Government work, public domain | Out-of-domain JDs — different sector, different register |
| Synthetic candidates | generated here | Everything, at every stage |

```
real Djinni JDs   ──→  skill co-occurrence, experience bands, seniority mix
                            ↓
                       synthetic JD generation          →  training set

real Djinni JDs   ──→  sampled directly, opponents generated cross-family  →  RecruitHard
real USAJOBS JDs  ──→  same                                                →  OOD set

synthetic candidates (structured ground truth retained)  →  all stages
real Djinni CVs   ──→  calibrating how realistic the resume renderer reads
                       — never a training label
```

**Candidates stay synthetic.** The Djinni CVs are MIT-licensed and anonymised by the
publisher, so using them would be legitimate, but a real resume has no known skill-level
annotation. Generating candidates from structured ground truth and rendering them into prose
is what makes the labels trustworthy without depending on a teacher model. Real CVs are used
only to check that the rendered ones read like the real thing.

Djinni is an IT job board, so the corpus skews to software. That suits a benchmark aimed at
CUDA and ML-infrastructure roles, and it bounds what can be claimed about generalisation:
out-of-domain means *other IT domains*, plus whatever USAJOBS adds.

**Open Recruiter user data never becomes training data.** Not automatically, not by opt-out.

---

## Phases

Each phase states what has to be true before the next one starts.

### Phase 0 — Skeleton, and an end-to-end loop that costs nothing

```
research/recruitgpt/
├── schemas.py              rich schema + mapping down to the SDK's Match
├── sources/
│   ├── djinni.py           load the MIT corpus, compute distributions
│   └── usajobs.py          fetch federal postings for the OOD set
├── data/
│   ├── generate.py         JD generation, structured candidates, resume renderer
│   ├── difficulty.py       five bands, and hard negatives
│   └── validate.py         rules + two teachers → gold / silver / ambiguous / rejected
├── splits.py               grouped split, to stop synthetic leakage
├── evaluation/
│   ├── bench.py            the RecruitBench runner
│   └── metrics.py          pairwise accuracy · NDCG@k · MRR · Recall@k · calibration
├── configs/
│   ├── debug.yaml          CPU, ten examples, stubbed teachers
│   └── qwen3_qlora.yaml
└── runs/                   one directory per run, config + metrics + manifest
```

**Done when:** `python -m recruitgpt.data.generate --config configs/debug.yaml` and
`python -m recruitgpt.evaluation.run --config configs/debug.yaml` both complete on CPU with no
API key. The output of this phase is a pipeline, not a dataset.

### Phase 1 — RecruitData at 1%, and a cost number

100 JDs · 300 candidates · 500 matching examples · 300 pairwise.

**Done when:**
- Measured token cost per example, extrapolated to a budget for the full target
- An assertion proves no template appears in both train and test after the grouped split
- The gold/silver/ambiguous/rejected distribution and the two-teacher disagreement rate are
  reported

**Decision point:** the full-scale target is chosen from that cost number, not from the
proposal's estimate.

### Phase 2 — RecruitBench v0 and the baselines

Built from Phase 1's held-out data. RecruitHard does not exist yet.

```
Qwen3-8B, no prompt engineering
Qwen3-8B + a carefully written recruiting prompt     ← the real opponent
Claude or GPT + the same prompt                      ← an upper reference
```

**Done when:** `metrics.json`, `predictions.jsonl`, and `error_analysis.jsonl` exist, and the
question *where does prompting systematically fail?* has an answer.

**Stop condition:** if the prompt baseline already handles the hard cases, stop and revisit
the research question. Finding this out here costs almost nothing; finding it out after a
training run does not.

### Phase 3 — RecruitGPT-SFT

Qwen3-8B + QLoRA. Target: listwise reranking — job plus compressed shortlist in, ordered list
with scores and reasons out.

**Done when:** it beats the Phase 2 prompt baseline on RecruitBench v0. If it does not, the
fix is in the data, not the hyperparameters.

### Phase 4 — Hard negatives, and RecruitHard

Mine high-confidence errors from SFT, categorise the failure modes, and build the frozen
benchmark from real JDs with cross-family opponents.

**Done when:** the synthetic-versus-human label agreement on the 200-pair calibration slice is
reported. Below threshold, the data pipeline is repaired before anything else proceeds.

### Phase 5 — RecruitGPT-Rank

Pairwise preferences → DPO, kept swappable rather than baked into the architecture.

**Done when:** pairwise accuracy on RecruitHard beats SFT, with an ablation showing what the
hard negatives contributed.

### Phase 6 — Into the product

```python
from recruitgpt import RecruitGPTRanker
r.ranker = TwoStageRanker(EmbeddingRanker(r.index), RecruitGPTRanker(), shortlist=50)
```

**Done when:** `check_architecture.py` passes, `pip install openrecruiter` still installs 97
packages with no training stack, and the desktop app works normally with `recruitgpt` absent.

---

## Boundaries

**Layout.** `research/recruitgpt/` holds data generation, training, and evaluation, and may
depend on whatever it needs. `sdk/recruitgpt/` holds only `RecruitGPTRanker`, lazy-loaded,
with torch behind an extra. CI enforces the line.

**Schema.** RecruitGPT's output is richer than the SDK's `Match` — skill coverage ratios, a
recommendation band. It is mapped down at the `Ranker.rank()` boundary. The SDK's types are
not extended for a model that does not exist yet; if a field proves its worth, it can be
promoted then.

**Weights.** Never in git. Hugging Face Hub, referenced by revision. `runs/` keeps config,
metrics, and a dataset manifest — enough to reproduce, not the artefacts themselves.

**Contributors.** `configs/debug.yaml` runs the whole pipeline on CPU with no API key. A GPU
is needed from phase 3, and not before.

---

## Not in v0.1

Fairness work — that is [`research/fairness/`](../fairness/), deliberately a separate track so
the two can publish separately. Agent training. Tool-use SFT. Microservices, Kubernetes, or
any distributed infrastructure.

---

## Intended contributions

Not "we trained a LoRA for recruiting".

- **RecruitData** — a controlled generation pipeline for recruiting training data
- **RecruitHard** — a benchmark where superficial signals give the wrong answer
- **RecruitBench** — a standard evaluation for recruiting models
- **RecruitGPT** — the specialised model itself
- **Hard-negative training** — a method for finding and correcting recruiting-specific
  reasoning failures

---

## Open questions

- What agreement rate on the human calibration slice is high enough to trust the synthetic
  labels? Pick the threshold before seeing the number.
- How far does a shortlist stretch before listwise reranking stops being affordable in the
  product, as opposed to possible in a benchmark?
- Does chunk-and-merge listwise reranking preserve the ordering quality of a single pass?

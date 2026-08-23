"""Prompt masking, against a real tokenizer.

Getting this wrong is the quietest failure in supervised fine-tuning: the model
spends its capacity learning to reproduce job descriptions, the loss falls, and
nothing in the logs looks unusual. So it is tested against the actual chat
template rather than a mock.
"""

from __future__ import annotations

import pytest

from recruitgpt_research.train.collate import IGNORE, Collator, encode

transformers = pytest.importorskip("transformers")

#: Small enough to download in CI, same family and template as the 8B base.
MODEL = "Qwen/Qwen3-0.6B"


@pytest.fixture(scope="module")
def tokenizer():
    return transformers.AutoTokenizer.from_pretrained(MODEL)


@pytest.fixture
def messages():
    return [
        {"role": "system", "content": "You are RecruitGPT."},
        {"role": "user", "content": "Rank these candidates."},
        {"role": "assistant", "content": '{"ranking": ["B", "A"]}'},
    ]


def _supervised(tokenizer, encoded) -> str:
    kept = [t for t, label in zip(encoded["input_ids"], encoded["labels"]) if label != IGNORE]
    return tokenizer.decode(kept)


def test_only_the_answer_is_supervised(tokenizer, messages):
    text = _supervised(tokenizer, encode(tokenizer, messages, 512))

    assert '{"ranking": ["B", "A"]}' in text
    assert "You are RecruitGPT" not in text, "the system prompt must not be a target"
    assert "Rank these candidates" not in text, "the user turn must not be a target"


def test_the_boundary_is_found_by_offset_not_by_token_count(tokenizer, messages):
    """The token sequences are not prefixes of one another even though the
    strings are — BPE merges differently once the next character is known. On
    Qwen3 the prompt ends `assistant\\n` and the full text continues
    `assistant\\n<think>`, so a length-based mask is off by one."""
    prompt_ids = tokenizer.apply_chat_template(
        messages[:-1], tokenize=True, add_generation_prompt=True
    )
    full_ids = tokenizer.apply_chat_template(messages, tokenize=True)

    assert full_ids[: len(prompt_ids)] != prompt_ids, (
        "if this ever holds, the naive approach would work and this test is stale"
    )
    # ...and the offset-based mask handles it anyway.
    assert '{"ranking"' in _supervised(tokenizer, encode(tokenizer, messages, 512))


def test_the_template_preamble_the_model_must_emit_is_supervised(tokenizer, messages):
    """Qwen3 renders `<think></think>` before the answer. At inference the model
    generates it, so it has to be trained on — masking it teaches the model to
    start with something it will never be prompted with."""
    assert "<think>" in _supervised(tokenizer, encode(tokenizer, messages, 512))


def test_the_masked_span_is_the_prompt_exactly(tokenizer, messages):
    encoded = encode(tokenizer, messages, 512)
    masked = [t for t, label in zip(encoded["input_ids"], encoded["labels"]) if label == IGNORE]
    rendered = tokenizer.apply_chat_template(
        messages[:-1], tokenize=False, add_generation_prompt=True
    )
    assert tokenizer.decode(masked) == rendered


def test_labels_and_inputs_stay_aligned(tokenizer, messages):
    encoded = encode(tokenizer, messages, 512)
    assert len(encoded["input_ids"]) == len(encoded["labels"]) == len(encoded["attention_mask"])
    for token, label in zip(encoded["input_ids"], encoded["labels"]):
        assert label in (IGNORE, token), "a label must be the token or masked, never another token"


def test_truncation_takes_from_the_prompt_not_the_answer(tokenizer, messages):
    """A clipped answer teaches the model to stop mid-JSON."""
    long = dict(messages[1], content="filler. " * 400)
    encoded = encode(tokenizer, [messages[0], long, messages[2]], 64)

    assert len(encoded["input_ids"]) == 64
    assert '{"ranking"' in _supervised(tokenizer, encoded)


def test_an_answer_that_cannot_fit_is_refused(tokenizer, messages):
    big = dict(messages[2], content='{"ranking": ' + '["X"], ' * 200 + "}")
    with pytest.raises(ValueError, match="does not fit"):
        encode(tokenizer, [messages[0], messages[1], big], 32)


def test_padding_is_masked_out(tokenizer, messages):
    """Otherwise the model learns to emit pad tokens."""
    short = encode(tokenizer, messages, 512)
    longer = encode(
        tokenizer, [messages[0], dict(messages[1], content="a " * 100), messages[2]], 512
    )
    batch = Collator(pad_token_id=tokenizer.pad_token_id)([short, longer])

    width = batch["input_ids"].shape[1]
    assert width == max(len(short["input_ids"]), len(longer["input_ids"]))
    padded_row = batch["labels"][0][len(short["input_ids"]) :]
    assert (padded_row == IGNORE).all()
    assert (batch["attention_mask"][0][len(short["input_ids"]) :] == 0).all()


def test_a_real_example_masks_correctly(tokenizer):
    """End to end, on the dataset the trainer actually consumes."""
    from recruitgpt_research.data.chat import to_chat
    from recruitgpt_research.data.synthetic import generate_examples

    chat = to_chat(generate_examples(1, seed=0)[0])
    text = _supervised(tokenizer, encode(tokenizer, chat.messages, 4096))

    assert '"ranking"' in text
    assert "## Job" not in text, "the job description must not be a target"
    assert "## Candidates" not in text

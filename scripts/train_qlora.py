"""Single-GPU NF4 LoRA experiment; saves an adapter, never deploys it."""
import argparse
import importlib.metadata
import json
import time
from pathlib import Path
from supportpilot.finetuning import load_training_splits, encode_example, pad_examples, file_sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/training/prepared")
    parser.add_argument("--output", default="runs/qlora-judgment-v1")
    parser.add_argument("--model", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--smoke", action="store_true", help="Two optimizer steps; not a quality experiment")
    parser.add_argument("--dry-run", action="store_true", help="Validate data and tokenize without GPU/model weights")
    args = parser.parse_args()
    if args.max_length < 128 or args.epochs < 1:
        parser.error("max-length must be >=128 and epochs >=1")
    output = Path(args.output)
    if not args.dry_run and output.exists():
        parser.error("Output exists; use a new --output to preserve the experiment")
    splits, manifest = load_training_splits(args.data)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded = {name: [encode_example(tokenizer, row, args.max_length) for row in rows] for name, rows in splits.items()}
    token_summary = {name: {"examples": len(rows), "max_tokens": max(len(r["input_ids"]) for r in rows), "supervised_tokens": sum(sum(t != -100 for t in r["labels"]) for r in rows)} for name, rows in encoded.items()}
    print(json.dumps(token_summary, indent=2))
    if args.dry_run:
        return
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainingArguments, set_seed
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        parser.error("A CUDA GPU with BF16 support is required")
    set_seed(20261010)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        args.model, revision=args.revision, torch_dtype=torch.bfloat16,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
        device_map={"": 0}, attn_implementation="sdpa",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], bias="none", task_type="CAUSAL_LM"))
    model.print_trainable_parameters()
    output.mkdir(parents=True, exist_ok=False)
    config = {"arguments": vars(args), "seed": 20261010, "dataset_manifest": manifest,
              "data_sha256": {name: file_sha(Path(args.data) / f"{name}.jsonl") for name in ("train", "validation")},
              "token_summary": token_summary, "base_revision": getattr(model.config, "_commit_hash", None),
              "gpu": torch.cuda.get_device_name(0), "torch_cuda": torch.version.cuda,
              "versions": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate")},
              "limitations": "Small template dataset. Smoke run is not quality evidence. Validation loss is not answer accuracy. Test set unused. Training prompts differ from runtime prompts."}
    (output / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    class EncodedDataset(torch.utils.data.Dataset):
        def __init__(self, rows):
            self.rows = rows
        def __len__(self):
            return len(self.rows)
        def __getitem__(self, index):
            return self.rows[index]
    def collate(rows):
        return {key: torch.tensor(value, dtype=torch.long) for key, value in pad_examples(rows, tokenizer.pad_token_id).items()}
    training_args = TrainingArguments(
        output_dir=str(output / "checkpoints"), per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=8, learning_rate=1e-4, num_train_epochs=args.epochs,
        max_steps=2 if args.smoke else -1, bf16=True, tf32=True,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch", warmup_ratio=0.1, weight_decay=0.01,
        eval_strategy="steps" if args.smoke else "epoch", save_strategy="steps" if args.smoke else "epoch",
        eval_steps=2, save_steps=2, logging_steps=1, save_total_limit=2,
        load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
        report_to="none", seed=20261010, data_seed=20261010, dataloader_num_workers=0,
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=EncodedDataset(encoded["train"]), eval_dataset=EncodedDataset(encoded["validation"]), data_collator=collate)
    result = trainer.train()
    validation = trainer.evaluate()
    trainer.save_model(str(output / "adapter"))
    tokenizer.save_pretrained(output / "adapter")
    report = {"smoke": args.smoke, "training": result.metrics, "validation": validation,
              "best_checkpoint": trainer.state.best_model_checkpoint,
              "elapsed_seconds_including_model_load": round(time.perf_counter() - started, 3),
              "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
              "peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 1024**3, 3),
              "test_used": False}
    (output / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

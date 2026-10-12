"""Paired base/adapter validation comparison on one identical NF4 base."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import random
import time
from supportpilot.finetuning import load_training_splits, file_sha
from supportpilot.judgment_eval import score, summarize
from supportpilot.judgment_revision import revise_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="runs/qlora-judgment-v1")
    parser.add_argument("--data", default="data/training/prepared")
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--selection-report", help="Frozen validation comparison used to select test settings")
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--correct-refund-reference", action="store_true")
    parser.add_argument("--prompt-profile", choices=["saved", "explicit-v2", "explicit-v3"], default="saved")
    args = parser.parse_args()
    if not 32 <= args.max_new_tokens <= 512:
        parser.error("max-new-tokens must be 32..512")
    if args.split == "test" and (args.correct_refund_reference or args.prompt_profile != "explicit-v3" or not args.selection_report):
        parser.error("test requires --prompt-profile explicit-v3 and --selection-report; reference corrections are prohibited")
    run = Path(args.run)
    config = json.loads((run / "run_config.json").read_text(encoding="utf-8"))
    adapter = run / "adapter"
    adapter_config = json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))
    splits, manifest = load_training_splits(args.data, include_test=args.split == "test")
    for name in ("train", "validation"):
        if file_sha(Path(args.data) / f"{name}.jsonl") != config["data_sha256"][name]:
            parser.error(f"{name} changed since training; use the original prepared dataset")
    model_id = config["arguments"]["model"]
    revision = config.get("base_revision") or config["arguments"]["revision"]
    if revision == "main":
        parser.error("Training did not record a base commit. Resolve the training revision before comparing")
    if adapter_config["base_model_name_or_path"] != model_id:
        parser.error("Adapter base model does not match training config")
    selection = None
    if args.split == "test":
        selection = json.loads(Path(args.selection_report).read_text(encoding="utf-8"))
        if (selection.get("split") != "validation" or selection.get("evaluator_version") != "judgment-comparison-1.2"
                or selection.get("prompt_profile") != args.prompt_profile or selection.get("base_revision") != revision
                or selection.get("model") != model_id or selection.get("settings", {}).get("max_new_tokens") != args.max_new_tokens
                or selection.get("dataset_sha256") != config["data_sha256"]["validation"]):
            parser.error("Selected validation report does not match frozen test settings")
        current_adapter = {p.name: file_sha(p) for p in sorted(adapter.iterdir()) if p.is_file()}
        if current_adapter != selection.get("adapter_sha256"):
            parser.error("Adapter changed since selected validation comparison")
    rows, corrections = revise_rows(splits[args.split], args.correct_refund_reference, args.prompt_profile)
    system_prompts = {task: next(r["messages"][0]["content"] for r in rows if r["task"] == task) for task in {r["task"] for r in rows}}
    if selection is not None and system_prompts != selection.get("system_prompts"):
        parser.error("System prompts changed since selected validation comparison")
    for row in rows:
        reference = score(row, row["messages"][2]["content"])
        if not reference["passed"]:
            parser.error(f"Invalid reference: {row['id']}")
    from transformers import AutoTokenizer
    # Shared saved training tokenizer for BOTH conditions.
    tokenizer = AutoTokenizer.from_pretrained(adapter)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    prompts = {}
    for row in rows:
        ids = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=True, add_generation_prompt=True, enable_thinking=False)
        if len(ids) + args.max_new_tokens > 4096:
            parser.error(f"Context budget exceeded: {row['id']}")
        prompts[row["id"]] = ids
    print(f"Validated {len(rows)} {args.split} records. Test used: {args.split == 'test'}. Base revision: {revision}")
    if args.dry_run:
        return
    protocol = None
    if args.split == "test":
        protocol = {"evaluator_version": "judgment-comparison-1.2", "prompt_profile": args.prompt_profile,
                    "base_revision": revision, "max_new_tokens": args.max_new_tokens,
                    "test_sha256": file_sha(Path(args.data) / "test.jsonl"),
                    "selection_report_sha256": file_sha(args.selection_report), "adapter_sha256": current_adapter,
                    "code_sha256": {name: file_sha(Path(__file__).resolve().parents[1] / name) for name in
                                    ("scripts/compare_qlora.py", "supportpilot/judgment_eval.py", "supportpilot/judgment_revision.py", "supportpilot/finetuning.py")}}
        protocol_path = run / "test_protocol.json"
        if protocol_path.exists():
            if json.loads(protocol_path.read_text(encoding="utf-8")) != protocol:
                parser.error("Test protocol already frozen with different settings; preserve the first experiment")
        else:
            with protocol_path.open("x", encoding="utf-8") as stream:
                json.dump(protocol, stream, ensure_ascii=False, indent=2)
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, set_seed
    from peft import PeftModel
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        parser.error("CUDA with BF16 is required")
    set_seed(20261010)
    base = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, torch_dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="sdpa",
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
    )
    model = PeftModel.from_pretrained(base, adapter, is_trainable=False)
    model.eval()
    model.config.use_cache = True
    def generate(row, mode):
        inputs = torch.tensor([prompts[row["id"]]], dtype=torch.long, device="cuda:0")
        mask = torch.ones_like(inputs)
        with (model.disable_adapter() if mode == "base" else nullcontext()), torch.inference_mode():
            torch.cuda.synchronize()
            started = time.perf_counter()
            tokens = model.generate(input_ids=inputs, attention_mask=mask, do_sample=False,
                                    num_beams=1, repetition_penalty=1.0, max_new_tokens=args.max_new_tokens,
                                    pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
                                    use_cache=True)
            generated = tokens[0, inputs.shape[1]:].tolist()
            text = tokenizer.decode(generated, skip_special_tokens=True)
            torch.cuda.synchronize()
            elapsed = (time.perf_counter() - started) * 1000
        ended = bool(generated) and generated[-1] == tokenizer.eos_token_id
        return text, elapsed, len(generated), len(generated) >= args.max_new_tokens and not ended
    # Same validation warmup for each condition, excluded from measurements.
    for mode in ("base", "adapter"):
        generate(rows[0], mode)
    torch.cuda.reset_peak_memory_stats()
    order = list(rows)
    random.Random(20261010).shuffle(order)
    cases = {"base": [], "adapter": []}
    for index, row in enumerate(order):
        modes = ("base", "adapter") if index % 2 == 0 else ("adapter", "base")
        for mode in modes:
            raw, elapsed, output_tokens, truncated = generate(row, mode)
            result = score(row, raw, truncated)
            cases[mode].append({"id": row["id"], "group_id": row["group_id"], "task": row["task"],
                                "raw": raw, "input_tokens": len(prompts[row["id"]]), "output_tokens": output_tokens,
                                "elapsed_ms": round(elapsed, 3), **result})
            print(f"{mode:7} {row['id']}: {'PASS' if result['passed'] else 'FAIL'} {elapsed:.1f} ms", flush=True)
    summary = {mode: summarize(values) for mode, values in cases.items()}
    base_passed = {r["id"]: r["passed"] for r in cases["base"]}
    paired = {"improved": [], "regressed": [], "both_passed": [], "both_failed": []}
    for row in cases["adapter"]:
        before, after = base_passed[row["id"]], row["passed"]
        label = ("both_passed" if after else "regressed") if before else ("improved" if after else "both_failed")
        paired[label].append(row["id"])
    report = {"evaluator_version": "judgment-comparison-1.2", "created_at": datetime.now(timezone.utc).isoformat(),
              "prompt_profile": args.prompt_profile, "reference_corrections": corrections,
              "system_prompts": system_prompts,
              "split": args.split, "test_used": args.split == "test", "model": model_id, "base_revision": revision,
              "test_protocol": protocol,
              "adapter": str(adapter), "dataset_sha256": file_sha(Path(args.data) / f"{args.split}.jsonl"),
              "dataset_manifest": manifest, "adapter_sha256": {p.name: file_sha(p) for p in sorted(adapter.iterdir()) if p.is_file()},
              "settings": {"quantization": "NF4-double-BF16", "do_sample": False, "max_new_tokens": args.max_new_tokens,
                           "warmup_per_mode": 1, "order_seed": 20261010, "timing": "synchronized generation and decode; excludes tokenization, model load, tensor transfer"},
              "versions": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft", "bitsandbytes")},
              "gpu": torch.cuda.get_device_name(0),
              "shared_peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
              "summary": summary, "paired": paired, "cases": cases,
              "limitations": "Small template set with correlated paraphrases; see split field. Validation used for checkpoint/prompt selection. Test uses original reference labels and unchanged selected prompt. Exact reference IDs are a proxy, not semantic correctness. Shared NF4 base; disabled adapter remains resident. Single timing sample; not a serving benchmark. No automatic deployment."}
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    path = directory / f"qlora-{'test' if args.split == 'test' else 'comparison'}-{time.time_ns()}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"summary": summary, "paired": paired, "report": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

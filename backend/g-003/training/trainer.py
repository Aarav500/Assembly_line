import os
import json
from typing import Callable, Optional

import torch
from datasets import Dataset, DatasetDict
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
    TrainerCallback,
    TrainerControl,
    TrainerState,
)
from peft import LoraConfig, TaskType, get_peft_model


def _iter_text_records(dataset_path: str):
    # Gather .jsonl and .txt files
    for root, _, files in os.walk(dataset_path):
        for f in files:
            if f.lower().endswith('.jsonl'):
                p = os.path.join(root, f)
                with open(p, 'r', encoding='utf-8') as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                if 'text' in obj and isinstance(obj['text'], str):
                                    yield {"text": obj['text']}
                                elif 'instruction' in obj and 'output' in obj:
                                    inst = obj.get('instruction', '')
                                    inp = obj.get('input', '')
                                    out = obj.get('output', '')
                                    text = f"Instruction: {inst}\nInput: {inp}\nOutput: {out}"
                                    yield {"text": text}
                            elif isinstance(obj, str):
                                yield {"text": obj}
                        except Exception:
                            continue
            elif f.lower().endswith('.txt'):
                p = os.path.join(root, f)
                with open(p, 'r', encoding='utf-8') as fh:
                    text = fh.read()
                    yield {"text": text}


def _load_dataset(dataset_path: str) -> DatasetDict:
    def gen():
        for rec in _iter_text_records(dataset_path):
            yield rec
    ds = Dataset.from_generator(gen)
    # simple split: 95/5
    if len(ds) >= 20:
        split = ds.train_test_split(test_size=0.05, seed=42)
        return DatasetDict({'train': split['train'], 'eval': split['test']})
    else:
        return DatasetDict({'train': ds, 'eval': ds.select(range(0))})


class CancelCallback(TrainerCallback):
    def __init__(self, cancel_event, log_fn: Callable[[str], None] = None):
        self.cancel_event = cancel_event
        self.log_fn = log_fn or (lambda _: None)

    def on_step_end(self, args, state: TrainerState, control: TrainerControl, **kwargs):
        if self.cancel_event is not None and self.cancel_event.is_set():
            self.log_fn('Cancellation requested. Stopping training...')
            control.should_training_stop = True
        return control


def run_causal_lm_training(config: dict, output_dir: str, log_fn: Callable[[str], None], cancel_event: Optional[object] = None):
    os.makedirs(output_dir, exist_ok=True)

    model_name = config['model_name']
    dataset_path = config['dataset_path']
    block_size = int(config.get('block_size', 1024))

    log_fn(f"Loading dataset from {dataset_path}")
    dsdict = _load_dataset(dataset_path)

    log_fn(f"Loading tokenizer and model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize_fn(examples):
        return tokenizer(examples['text'], truncation=True, max_length=block_size)

    tokenized = dsdict.map(tokenize_fn, batched=True, remove_columns=dsdict['train'].column_names)
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    model = AutoModelForCausalLM.from_pretrained(model_name)

    if bool(config.get('lora', True)):
        log_fn('Applying LoRA adapters')
        lora_config = LoraConfig(
            r=int(config.get('lora_r', 8)),
            lora_alpha=int(config.get('lora_alpha', 16)),
            lora_dropout=float(config.get('lora_dropout', 0.05)),
            bias='none',
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_config)

    fp16 = bool(config.get('fp16', True)) and torch.cuda.is_available()
    bf16 = bool(config.get('bf16', False)) and torch.cuda.is_available()

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=float(config.get('num_train_epochs', 1.0)),
        learning_rate=float(config.get('learning_rate', 2e-5)),
        per_device_train_batch_size=int(config.get('per_device_train_batch_size', 2)),
        per_device_eval_batch_size=int(config.get('per_device_eval_batch_size', 2)),
        gradient_accumulation_steps=int(config.get('gradient_accumulation_steps', 1)),
        warmup_steps=int(config.get('warmup_steps', 0)),
        weight_decay=float(config.get('weight_decay', 0.0)),
        max_steps=int(config.get('max_steps', -1)),
        save_steps=int(config.get('save_steps', 1000)),
        logging_steps=int(config.get('logging_steps', 50)),
        eval_steps=int(config.get('eval_steps', 200)),
        evaluation_strategy=config.get('evaluation_strategy', 'no'),
        report_to=[],
        fp16=fp16,
        bf16=bf16,
        seed=int(config.get('seed', 42)),
        save_total_limit=2,
    )

    callbacks = []
    if cancel_event is not None:
        callbacks.append(CancelCallback(cancel_event=cancel_event, log_fn=log_fn))

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized['train'],
        eval_dataset=tokenized.get('eval'),
        tokenizer=tokenizer,
        data_collator=data_collator,
        callbacks=callbacks,
    )

    log_fn('Starting Trainer.train()')
    trainer.train()

    log_fn('Saving model and tokenizer')
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    if bool(config.get('push_to_hub', False)):
        repo_id = config.get('hub_model_id')
        private = bool(config.get('hub_private_repo', False))
        if repo_id:
            log_fn(f'Pushing to Hub: {repo_id} (private={private})')
            try:
                trainer.push_to_hub()
            except Exception as e:
                log_fn(f'Failed to push to hub: {e}')


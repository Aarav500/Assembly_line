import threading
import time
import uuid
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from downstream import DownstreamClient
from token_opt import TokenOptimizer
from utils import now_s, compute_request_hash, join_messages_as_text

class Job:
    def __init__(self, job_id: str, payload: Dict[str, Any], cache_key: str):
        self.id = job_id
        self.payload = payload
        self.cache_key = cache_key
        self.response = None
        self.error = None
        self.event = threading.Event()

    def set_result(self, response: Dict[str, Any]):
        self.response = response
        self.event.set()

    def set_error(self, error: Exception):
        self.error = error
        self.event.set()

    def wait(self, timeout: float):
        if not self.event.wait(timeout):
            raise TimeoutError("Job wait timeout")
        if self.error:
            raise self.error
        return self.response

class BatchQueue:
    def __init__(self, key: str, config, downstream: DownstreamClient, optimizer: TokenOptimizer, cache):
        self.key = key
        self.config = config
        self.downstream = downstream
        self.optimizer = optimizer
        self.cache = cache
        self.jobs: List[Job] = []
        self.lock = threading.Lock()
        self.timer = None

    def enqueue(self, job: Job):
        with self.lock:
            self.jobs.append(job)
            # Schedule flush if not already scheduled
            if self.timer is None:
                self.timer = threading.Timer(self.config.BATCH_WINDOW_MS / 1000.0, self.flush)
                self.timer.daemon = True
                self.timer.start()
            # Immediate flush if reached max size
            if len(self.jobs) >= self.config.MAX_BATCH_SIZE:
                try:
                    self.timer.cancel()
                except Exception:
                    pass
                self.timer = None
                # Flush in a separate thread to avoid blocking enqueue
                threading.Thread(target=self.flush, daemon=True).start()

    def _gather_jobs(self) -> List[Job]:
        with self.lock:
            jobs = self.jobs[: self.config.MAX_BATCH_SIZE]
            self.jobs = self.jobs[self.config.MAX_BATCH_SIZE :]
            if not self.jobs:
                self.timer = None
            else:
                # Reschedule another timer for remaining jobs
                try:
                    if self.timer:
                        self.timer.cancel()
                except Exception:
                    pass
                self.timer = threading.Timer(self.config.BATCH_WINDOW_MS / 1000.0, self.flush)
                self.timer.daemon = True
                self.timer.start()
            return jobs

    def flush(self):
        jobs = self._gather_jobs()
        if not jobs:
            return

        # Build batched request from jobs
        try:
            messages_list = [j.payload["messages"] for j in jobs]
            first_payload = jobs[0].payload
            model = first_payload["model"]
            temperature = first_payload["temperature"]
            top_p = first_payload["top_p"]
            max_tokens = first_payload["max_tokens"]

            # We assume batch_key ensures same system prompt signature & model/params
            system_prompt = self.optimizer.extract_system_prompt(messages_list[0]) or "You are a helpful assistant."

            items = []
            for j, messages in zip(jobs, messages_list):
                condensed = self.optimizer.condense_messages_for_batch(messages)
                items.append({"id": j.id, "content": condensed})

            batched_messages = self._build_batched_messages(system_prompt=system_prompt, items=items)

            response = self.downstream.send_chat_completion(
                messages=batched_messages,
                model=model,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            mapping = self._parse_batched_response(response)

            # Distribute results; fallback to per-item call if missing
            for job in jobs:
                item_text = mapping.get(job.id)
                if item_text is None:
                    # Fallback: call downstream individually for this job
                    try:
                        single_resp = self.downstream.send_chat_completion(
                            messages=job.payload["messages"],
                            model=model,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=max_tokens,
                        )
                        job.set_result(single_resp)
                        self.cache.set(job.cache_key, single_resp)
                    except Exception as e:
                        job.set_error(e)
                else:
                    # Wrap into single-response format
                    single = {
                        "id": f"cmpl-{uuid.uuid4().hex}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": item_text.strip()},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    job.set_result(single)
                    self.cache.set(job.cache_key, single)
        except Exception as e:
            for job in jobs:
                job.set_error(e)

    def _build_batched_messages(self, system_prompt: str, items: List[Dict[str, str]]):
        # Add strict formatting instruction to the system prompt to ensure parseable outputs
        system = (
            system_prompt.strip()
            + "\n\nYou will receive multiple items. For each <item id=\"...\">, produce a standalone answer.\n"
              "Output strictly in XML tags, one per item: <answer id=\"same id\"> ... </answer>. Do not add any extra commentary."
        )
        # Build a single user message containing all items
        parts = ["Process the following items and reply with answers using the exact requested XML tags:"]
        for it in items:
            parts.append(f"<item id=\"{it['id']}\">\n{it['content'].strip()}\n</item>")
        user = "\n\n".join(parts)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _parse_batched_response(self, downstream_response: Dict[str, Any]) -> Dict[str, str]:
        # Extract assistant content
        try:
            text = downstream_response["choices"][0]["message"]["content"]
        except Exception:
            text = ""
        if not text:
            return {}
        pattern = re.compile(r"<answer\\s+id=\"([^\"]+)\">([\\s\\S]*?)</answer>", re.IGNORECASE)
        mapping: Dict[str, str] = {}
        for m in pattern.finditer(text):
            ans_id = m.group(1).strip()
            content = m.group(2).strip()
            mapping[ans_id] = content
        return mapping

class BatchManager:
    def __init__(self, config, cache):
        self.config = config
        self.cache = cache
        self.downstream = DownstreamClient(config)
        self.optimizer = TokenOptimizer(config=config)
        self.queues: Dict[str, BatchQueue] = {}
        self.lock = threading.Lock()

    def _batch_key_for(self, payload: Dict[str, Any]) -> str:
        messages = payload["messages"]
        model = payload["model"]
        temperature = payload["temperature"]
        top_p = payload["top_p"]
        system_prompt = self.optimizer.extract_system_prompt(messages) or ""
        key = compute_request_hash({
            "model": model,
            "temperature": temperature,
            "top_p": top_p,
            "system": system_prompt,
        })
        return key

    def _get_queue(self, key: str) -> BatchQueue:
        with self.lock:
            q = self.queues.get(key)
            if q is None:
                q = BatchQueue(key, self.config, self.downstream, self.optimizer, self.cache)
                self.queues[key] = q
            return q

    def enqueue_and_wait(self, messages: List[Dict[str, str]], model: str, temperature: float, top_p: float, max_tokens: int, cache_key: str, timeout_seconds: float):
        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        job_id = uuid.uuid4().hex
        job = Job(job_id, payload, cache_key)
        batch_key = self._batch_key_for(payload)
        queue = self._get_queue(batch_key)
        queue.enqueue(job)
        return job.wait(timeout_seconds)


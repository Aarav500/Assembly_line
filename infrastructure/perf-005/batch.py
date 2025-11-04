import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from queue import Queue, Empty
from datetime import datetime


class BatchStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ChunkStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ItemResult:
    item_id: str
    status: str  # "success" | "failed" | "cancelled"
    input: Any = None
    output: Any = None
    error: Optional[str] = None


@dataclass
class Chunk:
    id: str
    index: int
    status: ChunkStatus = ChunkStatus.PENDING
    size: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    # items are the raw inputs for this chunk (list of dicts with id, data, flags)
    items: List[Dict[str, Any]] = field(default_factory=list)
    results: List[ItemResult] = field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "status": self.status,
            "size": self.size,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
        }


@dataclass
class Batch:
    id: str
    status: BatchStatus = BatchStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    operation: str = "echo"
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_size: int = 50
    total_items: int = 0
    processed_items: int = 0
    success_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    chunks: List[Chunk] = field(default_factory=list)
    cancel_flag: bool = False

    def progress_percent(self) -> int:
        if self.total_items <= 0:
            return 0
        pct = int((self.processed_items / self.total_items) * 100)
        if pct > 100:
            return 100
        return pct

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "operation": self.operation,
            "metadata": self.metadata,
            "chunk_size": self.chunk_size,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "progress_percent": self.progress_percent(),
            "chunks": [c.to_summary() for c in self.chunks],
        }


class InMemoryStore:
    def __init__(self):
        self._batches: Dict[str, Batch] = {}
        self._lock = threading.RLock()

    def create_batch(self, batch: Batch):
        with self._lock:
            self._batches[batch.id] = batch

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        with self._lock:
            return self._batches.get(batch_id)

    def update_batch(self, batch: Batch):
        with self._lock:
            self._batches[batch.id] = batch

    def with_lock(self):
        return self._lock


class OperationExecutor:
    @staticmethod
    def execute(operation: str, data: Any) -> Any:
        # Expandable set of simple demo operations
        if operation == "echo":
            return data
        if operation == "reverse":
            if isinstance(data, str):
                return data[::-1]
            raise ValueError("reverse operation requires string input")
        if operation == "uppercase":
            if isinstance(data, str):
                return data.upper()
            raise ValueError("uppercase operation requires string input")
        if operation == "sum":
            if isinstance(data, list):
                try:
                    return sum(float(x) for x in data)
                except Exception:
                    raise ValueError("sum operation requires list of numbers")
            raise ValueError("sum operation requires list input")
        if operation == "sleep":
            # data can be seconds; simulate latency
            try:
                secs = float(data)
            except Exception:
                secs = 0.1
            time.sleep(max(0.0, min(secs, 2.0)))
            return {"slept": secs}
        # default noop
        return data


class WorkerPool:
    def __init__(self, store: InMemoryStore, worker_count: int = 4):
        self.store = store
        self.queue: Queue[Tuple[str, str]] = Queue()
        self.worker_count = worker_count
        self.threads: List[threading.Thread] = []
        self._running = False
        self._start_lock = threading.Lock()

    def start(self):
        with self._start_lock:
            if self._running:
                return
            self._running = True
            for i in range(self.worker_count):
                t = threading.Thread(target=self._worker_loop, name=f"worker-{i}", daemon=True)
                t.start()
                self.threads.append(t)

    def stop(self):
        self._running = False
        # Put sentinels to unblock threads
        for _ in self.threads:
            self.queue.put(("__STOP__", "__STOP__"))
        for t in self.threads:
            t.join(timeout=1.0)

    def submit_chunk(self, batch_id: str, chunk_id: str):
        self.queue.put((batch_id, chunk_id))

    def _worker_loop(self):
        while self._running:
            try:
                batch_id, chunk_id = self.queue.get(timeout=0.5)
            except Empty:
                continue
            if batch_id == "__STOP__":
                break
            try:
                self._process_chunk(batch_id, chunk_id)
            except Exception:
                # Best-effort: mark chunk failed
                with self.store.with_lock():
                    batch = self.store.get_batch(batch_id)
                    if not batch:
                        continue
                    chunk = next((c for c in batch.chunks if c.id == chunk_id), None)
                    if chunk and chunk.status not in (ChunkStatus.COMPLETED, ChunkStatus.CANCELLED):
                        chunk.status = ChunkStatus.FAILED
                        chunk.finished_at = datetime.utcnow().isoformat() + "Z"
                        # mark whole chunk items as failed if not already set
                        for item in chunk.items[len(chunk.results):]:
                            chunk.results.append(
                                ItemResult(item_id=item["id"], status="failed", input=item.get("data"), output=None, error="Worker error")
                            )
                            chunk.failed_count += 1
                        # update batch counters
                        added_processed = chunk.success_count + chunk.failed_count + chunk.cancelled_count
                        batch.processed_items += added_processed
                        batch.failed_count += chunk.failed_count
                        batch.success_count += chunk.success_count
                        batch.cancelled_count += chunk.cancelled_count
                        self._update_batch_overall_status_locked(batch)
                        self.store.update_batch(batch)
            finally:
                self.queue.task_done()

    def _process_chunk(self, batch_id: str, chunk_id: str):
        with self.store.with_lock():
            batch = self.store.get_batch(batch_id)
            if not batch:
                return
            chunk = next((c for c in batch.chunks if c.id == chunk_id), None)
            if not chunk or chunk.status not in (ChunkStatus.PENDING,):
                return
            # mark running
            chunk.status = ChunkStatus.RUNNING
            chunk.started_at = datetime.utcnow().isoformat() + "Z"
            if batch.status == BatchStatus.PENDING:
                batch.status = BatchStatus.RUNNING
                batch.started_at = batch.started_at or datetime.utcnow().isoformat() + "Z"
            self.store.update_batch(batch)

        # process items outside lock
        for item in chunk.items:
            with self.store.with_lock():
                batch = self.store.get_batch(batch_id)
                if not batch:
                    return
                cancelled = batch.cancel_flag
            if cancelled:
                # mark remaining items as cancelled
                with self.store.with_lock():
                    if chunk.status == ChunkStatus.RUNNING:
                        chunk.results.append(
                            ItemResult(item_id=item["id"], status="cancelled", input=item.get("data"), output=None, error="Batch cancelled")
                        )
                        chunk.cancelled_count += 1
                    continue
            # execute operation with per-item failure handling
            try:
                # forced failure support
                if item.get("should_fail"):
                    raise ValueError("Forced failure for item")
                result = OperationExecutor.execute(batch.operation, item.get("data"))
                with self.store.with_lock():
                    chunk.results.append(
                        ItemResult(item_id=item["id"], status="success", input=item.get("data"), output=result, error=None)
                    )
                    chunk.success_count += 1
            except Exception as ex:
                with self.store.with_lock():
                    chunk.results.append(
                        ItemResult(item_id=item["id"], status="failed", input=item.get("data"), output=None, error=str(ex))
                    )
                    chunk.failed_count += 1

        # finalize chunk and update batch counters
        with self.store.with_lock():
            batch = self.store.get_batch(batch_id)
            if not batch:
                return
            if batch.cancel_flag and chunk.cancelled_count > 0 and (chunk.success_count + chunk.failed_count) < chunk.size:
                chunk.status = ChunkStatus.CANCELLED
            else:
                # completed even if some failed
                chunk.status = ChunkStatus.COMPLETED
            chunk.finished_at = datetime.utcnow().isoformat() + "Z"

            # update batch counters by adding this chunk's counts
            batch.processed_items += (chunk.success_count + chunk.failed_count + chunk.cancelled_count)
            batch.success_count += chunk.success_count
            batch.failed_count += chunk.failed_count
            batch.cancelled_count += chunk.cancelled_count

            # if all chunks in terminal state, set batch terminal state
            self._update_batch_overall_status_locked(batch)
            self.store.update_batch(batch)

    def _update_batch_overall_status_locked(self, batch: Batch):
        all_terminal = all(c.status in (ChunkStatus.COMPLETED, ChunkStatus.CANCELLED, ChunkStatus.FAILED) for c in batch.chunks)
        if not all_terminal:
            batch.status = BatchStatus.RUNNING if not batch.cancel_flag else BatchStatus.CANCELLED
            return
        # all chunks finished/cancelled/failed
        if batch.cancel_flag or (batch.cancelled_count > 0 and batch.success_count + batch.failed_count < batch.total_items):
            batch.status = BatchStatus.CANCELLED
        elif batch.failed_count == 0 and batch.cancelled_count == 0:
            batch.status = BatchStatus.COMPLETED
        elif batch.success_count == 0 and (batch.failed_count > 0):
            batch.status = BatchStatus.FAILED
        else:
            batch.status = BatchStatus.PARTIAL
        batch.finished_at = datetime.utcnow().isoformat() + "Z"


def normalize_items(items: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in items:
        if isinstance(raw, dict):
            item_id = raw.get("id") or str(uuid.uuid4())
            data = raw.get("data", {k: v for k, v in raw.items() if k not in ("id", "should_fail")} if len(raw) > 1 else None)
            should_fail = bool(raw.get("should_fail", False))
            normalized.append({"id": item_id, "data": data, "should_fail": should_fail})
        else:
            normalized.append({"id": str(uuid.uuid4()), "data": raw, "should_fail": False})
    return normalized


def chunk_items(items: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def create_batch_from_items(items: List[Any], chunk_size: int, operation: str, metadata: Dict[str, Any]) -> Batch:
    normalized = normalize_items(items)
    batch_id = str(uuid.uuid4())
    batch = Batch(id=batch_id, chunk_size=chunk_size, operation=operation, metadata=metadata)
    batch.total_items = len(normalized)
    chs = chunk_items(normalized, chunk_size)
    for idx, group in enumerate(chs):
        ch = Chunk(id=str(uuid.uuid4()), index=idx, status=ChunkStatus.PENDING, size=len(group), items=group)
        batch.chunks.append(ch)
    return batch


def batch_results(batch: Batch, status: Optional[str] = None, offset: int = 0, limit: int = 100) -> Dict[str, Any]:
    # Flatten results
    results: List[Dict[str, Any]] = []
    for ch in batch.chunks:
        for r in ch.results:
            if status and r.status != status:
                continue
            results.append({
                "item_id": r.item_id,
                "status": r.status,
                "input": r.input,
                "output": r.output,
                "error": r.error,
                "chunk_id": ch.id,
                "chunk_index": ch.index,
            })
    total = len(results)
    results = results[offset: offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "items": results}


def retry_failed_items(batch: Batch) -> List[str]:
    # collect failed and cancelled items
    retry_items: List[Dict[str, Any]] = []
    for ch in batch.chunks:
        # map item_id -> item
        items_by_id = {it["id"]: it for it in ch.items}
        for r in ch.results:
            if r.status in ("failed", "cancelled"):
                # reuse original item data, clear should_fail to allow retry success unless user keeps it
                orig = items_by_id.get(r.item_id)
                if orig:
                    retry_items.append({"id": orig["id"], "data": orig.get("data"), "should_fail": orig.get("should_fail", False)})

    if not retry_items:
        return []

    # Create new chunks appended to the batch
    new_chunks_ids: List[str] = []
    groups = chunk_items(retry_items, batch.chunk_size)
    start_index = len(batch.chunks)
    for i, group in enumerate(groups):
        ch = Chunk(id=str(uuid.uuid4()), index=start_index + i, status=ChunkStatus.PENDING, size=len(group), items=group)
        batch.chunks.append(ch)
        new_chunks_ids.append(ch.id)
    return new_chunks_ids


import bdb
import os
import sys
import time
import uuid
import threading
import traceback
import inspect
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.getcwd())


def safe_relpath(path: str) -> str:
    ap = os.path.abspath(path)
    if ap.startswith(PROJECT_ROOT):
        return os.path.relpath(ap, PROJECT_ROOT)
    return ap


def safe_repr(value: Any, maxlen: int = 200) -> str:
    try:
        r = repr(value)
    except Exception as e:
        r = f"<unreprable {type(value).__name__}: {e}>"
    if len(r) > maxlen:
        return r[: maxlen - 3] + "..."
    return r


class WebBdb(bdb.Bdb):
    def __init__(self, session: "DebugSession"):
        super().__init__()
        self.session = session
        self.project_root = PROJECT_ROOT

    def user_line(self, frame):
        self._maybe_pause(frame, event_type="line")

    def user_call(self, frame, argument_list):
        # We don't pause on call by default to reduce noise.
        pass

    def user_return(self, frame, return_value):
        # Could capture returns as snapshots if desired.
        pass

    def user_exception(self, frame, exc_info):
        # If exception occurs, capture and pause if in user code
        self._maybe_pause(frame, event_type="exception", exc_info=exc_info)

    def _in_user_code(self, frame) -> bool:
        filename = os.path.abspath(frame.f_code.co_filename)
        return filename.startswith(self.project_root)

    def _maybe_pause(self, frame, event_type: str, exc_info=None):
        filename = os.path.abspath(frame.f_code.co_filename)
        lineno = frame.f_lineno
        funcname = frame.f_code.co_name
        if not self._in_user_code(frame):
            # Skip library/internal code: step to next line in this frame
            try:
                self.set_next(frame)
            except Exception:
                pass
            return
        # Build snapshot data
        local_vars = {}
        for k, v in frame.f_locals.items():
            if k.startswith("__") and k.endswith("__"):
                continue
            local_vars[k] = safe_repr(v)

        stack_summary: List[Dict[str, Any]] = []
        f = frame
        while f:
            fp = os.path.abspath(f.f_code.co_filename)
            stack_summary.append({
                "file": safe_relpath(fp),
                "line": f.f_lineno,
                "func": f.f_code.co_name,
            })
            f = f.f_back
        stack_summary.reverse()

        snap = {
            "file": safe_relpath(filename),
            "abs_file": filename,
            "line": lineno,
            "func": funcname,
            "event": event_type,
            "locals": local_vars,
            "stack": stack_summary,
            "time": time.time(),
        }
        if exc_info is not None:
            etype, evalue, etb = exc_info
            snap["exception"] = {
                "type": getattr(etype, "__name__", str(etype)),
                "message": str(evalue),
                "traceback": ''.join(traceback.format_exception(etype, evalue, etb))
            }
        self.session._pause_with_snapshot(snap, frame)

    def run_callable(self, callable_obj):
        # Start stepping so we stop inside user's callable
        self.set_step()
        return self.runcall(callable_obj)


class DebugSession:
    def __init__(self, target_callable, origin: Dict[str, Any]):
        self.session_id = str(uuid.uuid4())
        self.target_callable = target_callable
        self.origin = origin
        self.debugger = WebBdb(self)
        self.thread = threading.Thread(target=self._runner, name=f"DebugSession-{self.session_id}", daemon=True)
        self.status = "created"  # created, running, paused, finished, error, stopped
        self.error: Optional[str] = None
        self.snapshots: List[Dict[str, Any]] = []
        self.max_snapshots = 500
        self._lock = threading.Lock()
        self._pause_cond = threading.Condition(self._lock)
        self._waiting = False
        self._pending_action: Optional[str] = None
        self._current_frame = None
        self._current: Dict[str, Any] = {
            "file": None,
            "abs_file": None,
            "line": None,
            "func": None,
            "stack": [],
            "locals": {},
            "event": None,
        }
        self._breaks: Dict[str, List[int]] = {}

    def start(self):
        with self._lock:
            self.status = "running"
        self.thread.start()

    def _runner(self):
        try:
            self.debugger.run_callable(self.target_callable)
            with self._lock:
                if self.status not in ("stopped", "error"):
                    self.status = "finished"
        except bdb.BdbQuit:
            with self._lock:
                self.status = "stopped"
        except SystemExit as e:
            with self._lock:
                self.status = "finished"
        except Exception:
            err = traceback.format_exc()
            with self._lock:
                self.error = err
                self.status = "error"
        finally:
            # Ensure any waiters are released
            with self._lock:
                self._waiting = False
                self._pending_action = None
                self._current_frame = None
                self._pause_cond.notify_all()

    def _pause_with_snapshot(self, snap: Dict[str, Any], frame):
        with self._lock:
            self.status = "paused"
            # update current
            self._current.update({
                "file": snap["file"],
                "abs_file": snap["abs_file"],
                "line": snap["line"],
                "func": snap["func"],
                "stack": snap["stack"],
                "locals": snap["locals"],
                "event": snap["event"],
            })
            # store snapshot
            snap_id = len(self.snapshots)
            snap_rec = dict(snap)
            snap_rec["id"] = snap_id
            self.snapshots.append(snap_rec)
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots.pop(0)
                # Adjust IDs to maintain uniqueness; in UI they are used read-only; we won't compact IDs for simplicity
            self._current_frame = frame
            self._waiting = True
            self._pending_action = None
            self._pause_cond.notify_all()
            # Wait for command
            while self._waiting and self.status == "paused":
                self._pause_cond.wait(timeout=0.1)
                if self._pending_action:
                    action = self._pending_action
                    self._pending_action = None
                    # apply action and resume
                    if action == "step":
                        self.debugger.set_step()
                        self._waiting = False
                    elif action == "next":
                        if self._current_frame is not None:
                            self.debugger.set_next(self._current_frame)
                        else:
                            self.debugger.set_step()
                        self._waiting = False
                    elif action == "continue":
                        self.debugger.set_continue()
                        self._waiting = False
                    elif action == "stop":
                        self.debugger.set_quit()
                        self._waiting = False
                        self.status = "stopped"
                    else:
                        # Unknown action: ignore and keep waiting
                        pass
        # When we leave the lock, debugger continues

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "status": self.status,
                "error": self.error,
                "current": dict(self._current) if self._current else None,
                "snapshots_count": len(self.snapshots),
                "breakpoints": self.list_breakpoints(),
                "origin": self.origin,
            }

    def command(self, action: str) -> Tuple[bool, str]:
        with self._lock:
            if self.status not in ("paused", "running"):
                return False, f"Session is {self.status}"
            # If running, only stop is allowed
            if self.status == "running" and action != "stop":
                return False, "Session is running; wait until paused or issue stop"
            # Set action
            self._pending_action = action
            # Switch to running; actual status change to running will happen when debugger continues
            if action in ("step", "next", "continue"):
                self.status = "running"
            self._waiting = False
            self._pause_cond.notify_all()
            return True, ""

    def stop(self):
        with self._lock:
            if self.status in ("finished", "stopped", "error"):
                return
            self._pending_action = "stop"
            self._waiting = False
            self.status = "stopped"
            self._pause_cond.notify_all()

    def add_breakpoint(self, abs_file: str, line: int) -> Tuple[bool, str]:
        with self._lock:
            try:
                self.debugger.set_break(abs_file, line)
            except Exception as e:
                return False, f"Failed to set breakpoint: {e}"
            rel = safe_relpath(abs_file)
            self._breaks.setdefault(rel, [])
            if line not in self._breaks[rel]:
                self._breaks[rel].append(line)
            return True, ""

    def remove_breakpoint(self, abs_file: str, line: int) -> Tuple[bool, str]:
        with self._lock:
            try:
                self.debugger.clear_break(abs_file, line)
            except Exception as e:
                return False, f"Failed to clear breakpoint: {e}"
            rel = safe_relpath(abs_file)
            if rel in self._breaks and line in self._breaks[rel]:
                self._breaks[rel].remove(line)
                if not self._breaks[rel]:
                    del self._breaks[rel]
            return True, ""

    def list_breakpoints(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for rel, lines in self._breaks.items():
            for ln in sorted(lines):
                result.append({"file": rel, "line": ln})
        return result

    def list_snapshots(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": s.get("id", i),
                    "file": s.get("file"),
                    "line": s.get("line"),
                    "func": s.get("func"),
                    "event": s.get("event"),
                    "time": s.get("time"),
                }
                for i, s in enumerate(self.snapshots)
            ]

    def get_snapshot(self, snap_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            if 0 <= snap_id < len(self.snapshots):
                # Return a copy to avoid mutation
                snap = dict(self.snapshots[snap_id])
                # Remove abs_file for security; return rel path
                if "abs_file" in snap:
                    snap["file"] = snap.get("file") or safe_relpath(snap["abs_file"]) 
                    snap.pop("abs_file", None)
                return snap
            return None


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, DebugSession] = {}
        self._lock = threading.Lock()

    def create_session(self, target_callable, origin: Dict[str, Any]) -> DebugSession:
        sess = DebugSession(target_callable, origin)
        with self._lock:
            self._sessions[sess.session_id] = sess
        sess.start()
        return sess

    def get_session(self, session_id: str) -> Optional[DebugSession]:
        with self._lock:
            return self._sessions.get(session_id)


session_manager = SessionManager()


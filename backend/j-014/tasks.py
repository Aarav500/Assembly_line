import time


class CancelledException(Exception):
    pass


def train_model(ctx, epochs: int = 10, epoch_time: float = 0.5, learning_rate: float = 0.001):
    epochs = max(1, int(epochs))
    epoch_time = max(0.01, float(epoch_time))
    ctx.log(f"Initializing training: epochs={epochs}, lr={learning_rate}")

    for epoch in range(1, epochs + 1):
        ctx.ensure_not_cancelled()
        # Simulate epoch steps
        steps = 5
        for s in range(steps):
            ctx.ensure_not_cancelled()
            time.sleep(epoch_time / steps)
        # Simulate metrics
        loss = max(0.0, 1.0 - epoch / epochs)
        acc = min(1.0, epoch / epochs)
        ctx.log(f"Epoch {epoch}/{epochs} - loss={loss:.4f}, acc={acc:.4f}")
        ctx.progress(int(epoch * 100 / epochs))

    ctx.log("Training finished successfully")


def long_task(ctx, steps: int = 20, step_time: float = 0.25):
    steps = max(1, int(steps))
    step_time = max(0.01, float(step_time))
    ctx.log(f"Starting long task: steps={steps}, step_time={step_time}s")
    for i in range(1, steps + 1):
        ctx.ensure_not_cancelled()
        time.sleep(step_time)
        ctx.log(f"Completed step {i}/{steps}")
        ctx.progress(int(i * 100 / steps))
    ctx.log("Long task finished")


TASKS = {
    'train_model': train_model,
    'long_task': long_task,
}


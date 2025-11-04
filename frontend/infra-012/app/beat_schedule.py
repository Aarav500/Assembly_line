from celery.schedules import crontab

def get_beat_schedule():
    return {
        "heartbeat-every-30s": {
            "task": "app.tasks.heartbeat",
            "schedule": 30.0,
            "options": {"queue": "low"},
        },
        "cleanup-daily-3am": {
            "task": "app.tasks.cleanup",
            "schedule": crontab(minute=0, hour=3),
            "options": {"queue": "low"},
        },
    }


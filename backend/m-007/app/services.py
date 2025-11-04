from datetime import datetime, timedelta
import random
from typing import Optional, List
import fnmatch

from .models import db, TestCase, TestRun, RetestJob, Owner, OwnershipRule
from flask import current_app


def get_or_create_test(name: str, path: Optional[str] = None) -> TestCase:
    test = TestCase.query.filter_by(name=name).first()
    if not test:
        test = TestCase(name=name, path=path)
        db.session.add(test)
        db.session.commit()
    else:
        if path and test.path != path:
            test.path = path
            db.session.commit()
    return test


def record_test_run(name: str, path: Optional[str], status: str, duration_ms: Optional[int], build_id: Optional[str], commit_sha: Optional[str], executed_at: Optional[datetime] = None) -> TestRun:
    status = status.lower()
    if status not in ["pass", "fail"]:
        raise ValueError("status must be 'pass' or 'fail'")

    test = get_or_create_test(name, path)
    maybe_assign_owner_for_test(test)

    run = TestRun(
        test_id=test.id,
        status=status,
        duration_ms=duration_ms,
        build_id=build_id,
        commit_sha=commit_sha,
        executed_at=executed_at or datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    return run


def maybe_assign_owner_for_test(test: TestCase) -> Optional[Owner]:
    if test.owner_id:
        return test.owner

    rules: List[OwnershipRule] = OwnershipRule.query.order_by(OwnershipRule.priority.asc(), OwnershipRule.created_at.asc()).all()
    target_path = test.path or ""
    for rule in rules:
        haystack = target_path if rule.scope == 'path' else test.name
        if haystack and fnmatch.fnmatchcase(haystack, rule.pattern):
            test.owner_id = rule.owner_id
            db.session.commit()
            return test.owner
    return None


def get_recent_runs(test: TestCase, window_size: int) -> List[TestRun]:
    return (
        TestRun.query.filter_by(test_id=test.id)
        .order_by(TestRun.executed_at.desc())
        .limit(window_size)
        .all()
    )


def compute_flakiness_score(test: TestCase, window_size: int, min_runs: int) -> Optional[float]:
    runs = list(reversed(get_recent_runs(test, window_size)))  # oldest to newest
    n = len(runs)
    if n < min_runs:
        return None

    pass_count = sum(1 for r in runs if r.status == 'pass')
    fail_count = n - pass_count

    pass_rate = pass_count / n
    fail_rate = fail_count / n

    variability = 1.0 - abs(pass_rate - fail_rate)  # 0..1

    transitions = 0
    for i in range(1, n):
        if runs[i].status != runs[i - 1].status:
            transitions += 1
    normalized_transitions = transitions / (n - 1) if n > 1 else 0.0

    score = 0.5 * variability + 0.5 * normalized_transitions
    return round(score, 4)


def analyze_and_schedule_for_test(test: TestCase) -> Optional[RetestJob]:
    cfg = current_app.config
    score = compute_flakiness_score(test, cfg['FLAKY_WINDOW_SIZE'], cfg['FLAKY_MIN_RUNS'])

    if score is None:
        return None

    test.flakiness_score = score
    test.last_analyzed_at = datetime.utcnow()
    db.session.commit()

    if score < cfg['FLAKINESS_THRESHOLD']:
        return None

    # Check cooldown and existing pending/running jobs
    pending = RetestJob.query.filter_by(test_id=test.id).filter(RetestJob.status.in_(['pending', 'running'])).first()
    if pending:
        return None

    cooldown_dt = datetime.utcnow() - timedelta(minutes=cfg['RETEST_COOLDOWN_MINUTES'])
    recent = RetestJob.query.filter_by(test_id=test.id).filter(RetestJob.scheduled_at >= cooldown_dt).first()
    if recent:
        return None

    # Ensure owner assignment
    maybe_assign_owner_for_test(test)

    job = RetestJob(
        test_id=test.id,
        owner_id=test.owner_id,
        status='pending',
        reason=f"Flaky score {score} >= threshold {cfg['FLAKINESS_THRESHOLD']}",
        scheduled_at=datetime.utcnow(),
    )
    db.session.add(job)
    db.session.commit()
    return job


def analyze_all_tests_and_schedule():
    tests = TestCase.query.all()
    scheduled = []
    for t in tests:
        job = analyze_and_schedule_for_test(t)
        if job:
            scheduled.append(job)
    return scheduled


def execute_one_retest(job: RetestJob) -> RetestJob:
    if job.status not in ['pending', 'failed']:
        return job

    job.status = 'running'
    job.started_at = datetime.utcnow()
    job.attempts += 1
    db.session.commit()

    # Simulate execution: outcome probability influenced by recent flakiness
    test = job.test
    cfg = current_app.config
    score = test.flakiness_score or compute_flakiness_score(test, cfg['FLAKY_WINDOW_SIZE'], cfg['FLAKY_MIN_RUNS']) or 0.0

    # Get last run status to correlate flakiness
    recent_runs = get_recent_runs(test, 1)
    last_status = recent_runs[0].status if recent_runs else 'pass'

    # Probability of flipping status increases with flakiness
    flip_prob = min(max(score, 0.1), 0.9)  # keep within sensible bounds
    flip = random.random() < flip_prob

    new_status = 'fail' if (last_status == 'pass' and flip) else ('pass' if (last_status == 'fail' and flip) else last_status)

    # Record retest run
    record_test_run(
        name=test.name,
        path=test.path,
        status=new_status,
        duration_ms=None,
        build_id=f"retest-{job.id}-{job.attempts}",
        commit_sha=None,
        executed_at=datetime.utcnow(),
    )

    job.status = 'completed'
    job.completed_at = datetime.utcnow()
    db.session.commit()

    return job


def execute_pending_retests(limit: int = 5):
    jobs = RetestJob.query.filter_by(status='pending').order_by(RetestJob.scheduled_at.asc()).limit(limit).all()
    executed = []
    for j in jobs:
        executed.append(execute_one_retest(j))
    return executed


def refresh_assignments_for_all_tests():
    tests = TestCase.query.all()
    assigned = 0
    for t in tests:
        before = t.owner_id
        maybe_assign_owner_for_test(t)
        if t.owner_id and t.owner_id != before:
            assigned += 1
    return assigned



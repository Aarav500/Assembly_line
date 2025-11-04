from models import db, RunHistory, PromptVersion
from sqlalchemy import func


def _safe_div(n, d):
    return (n / d) if d else 0.0


def compute_prompt_metrics(prompt_id: int) -> dict:
    # Summary across all versions
    q = db.session.query(
        func.count(RunHistory.id),
        func.avg(RunHistory.latency_ms),
        func.avg(RunHistory.score),
        func.sum(func.case((RunHistory.success == True, 1), else_=0))
    ).filter(RunHistory.prompt_id == prompt_id)
    total_runs, avg_latency, avg_score, total_success = q.first() or (0, None, None, 0)

    total_runs = int(total_runs or 0)
    avg_latency = round(float(avg_latency or 0), 2) if total_runs else 0
    avg_score = round(float(avg_score or 0), 4) if total_runs else 0
    pass_rate = round(_safe_div(int(total_success or 0), total_runs), 4) if total_runs else 0

    # Per version metrics
    # Get versions
    versions = (
        db.session.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt_id)
        .order_by(PromptVersion.version_number.asc())
        .all()
    )
    per_version = []
    for v in versions:
        qv = db.session.query(
            func.count(RunHistory.id),
            func.avg(RunHistory.latency_ms),
            func.avg(RunHistory.score),
            func.sum(func.case((RunHistory.success == True, 1), else_=0))
        ).filter(RunHistory.prompt_version_id == v.id)
        tr, al, ascore, ts = qv.first() or (0, None, None, 0)
        tr = int(tr or 0)
        al = round(float(al or 0), 2) if tr else 0
        ascore = round(float(ascore or 0), 4) if tr else 0
        pr = round(_safe_div(int(ts or 0), tr), 4) if tr else 0
        per_version.append({
            'version_id': v.id,
            'version_number': v.version_number,
            'total_runs': tr,
            'avg_latency_ms': al,
            'avg_score': ascore,
            'pass_rate': pr,
        })

    return {
        'summary': {
            'total_runs': total_runs,
            'avg_latency_ms': avg_latency,
            'avg_score': avg_score,
            'pass_rate': pass_rate,
        },
        'per_version': per_version
    }


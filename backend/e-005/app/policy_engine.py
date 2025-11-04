from datetime import timedelta
from typing import Dict, List, Tuple
from flask import current_app
from .models import db, DeletionLog, Policy
from .utils import glob_match, compile_regex, regex_match, parse_created, now_utc


class PolicyEngine:
    def __init__(self, registry_client):
        self.registry = registry_client

    def evaluate_policy(self, policy: Policy) -> Dict:
        summary = {
            'policy_id': policy.id,
            'name': policy.name,
            'repository_pattern': policy.repository_pattern,
            'simulate': policy.dry_run,
            'evaluated_repositories': 0,
            'candidate_deletions': 0,
            'kept': 0,
            'deleted_digests': [],
            'errors': [],
            'details': [],  # per repo details
        }

        repos = []
        try:
            repos = self.registry.list_repositories()
        except Exception as e:
            summary['errors'].append(f"Failed to list repositories: {e}")
            return summary

        keep_regex = compile_regex(policy.keep_tags_regex)
        exclude_regex = compile_regex(policy.exclude_tags_regex)
        protected = set((policy.protected_tags or '').split(',')) if policy.protected_tags else set()
        protected = {t.strip() for t in protected if t.strip()}

        max_age_cutoff = None
        if policy.max_age_days and policy.max_age_days > 0:
            max_age_cutoff = now_utc() - timedelta(days=policy.max_age_days)

        for repo in repos:
            if not glob_match(policy.repository_pattern, repo):
                continue
            try:
                repo_detail = self._evaluate_repo(policy, repo, keep_regex, exclude_regex, protected, max_age_cutoff)
                summary['evaluated_repositories'] += 1
                summary['candidate_deletions'] += len(repo_detail['deletions'])
                summary['kept'] += len(repo_detail['kept'])
                summary['details'].append(repo_detail)
            except Exception as e:
                summary['errors'].append(f"{repo}: {e}")

        return summary

    def _evaluate_repo(self, policy: Policy, repo: str, keep_regex, exclude_regex, protected: set, max_age_cutoff) -> Dict:
        tags = self.registry.list_tags(repo)
        items = []
        for tag in tags:
            try:
                meta = self.registry.tag_metadata(repo, tag)
                created_dt = parse_created(meta.get('created'))
                items.append({
                    'tag': tag,
                    'digest': meta.get('manifest_digest'),
                    'created': created_dt,
                })
            except Exception:
                items.append({
                    'tag': tag,
                    'digest': self.registry.head_manifest_digest(repo, tag),
                    'created': None,
                })

        # Sort by created desc for keep_last
        items_sorted = sorted(items, key=lambda i: (i['created'] is not None, i['created']), reverse=True)

        keep_set_tags = set()
        delete_candidates = []

        # Apply keep_last
        if policy.keep_last and policy.keep_last > 0:
            keep_set_tags.update([i['tag'] for i in items_sorted[:policy.keep_last]])

        for it in items:
            tag = it['tag']
            digest = it['digest']
            created = it['created']

            if tag in keep_set_tags or tag in { 'latest' } or tag in protected:
                continue

            if keep_regex and regex_match(keep_regex, tag):
                keep_set_tags.add(tag)
                continue

            if exclude_regex and regex_match(exclude_regex, tag):
                keep_set_tags.add(tag)
                continue

            # Age rule
            too_old = False
            if max_age_cutoff and created and created < max_age_cutoff:
                too_old = True

            # If no rules matched to keep, and either age rule says too old or keep_last didn't keep it
            # This means tag is candidate for deletion unless no age rule and keep_last is None -> do not delete everything by default
            if policy.max_age_days or policy.keep_last is not None:
                if (policy.max_age_days and too_old) or (policy.keep_last is not None and tag not in keep_set_tags):
                    delete_candidates.append({'tag': tag, 'digest': digest, 'created': created})

        # deduplicate by digest while preserving at least one tag label for logging
        deletions_by_digest = {}
        for c in delete_candidates:
            d = c['digest']
            if not d:
                # without digest we cannot delete; skip
                continue
            if d not in deletions_by_digest:
                deletions_by_digest[d] = { 'digest': d, 'tags': set(), 'created': c['created'] }
            deletions_by_digest[d]['tags'].add(c['tag'])

        kept_list = [i['tag'] for i in items if i['tag'] in keep_set_tags]

        return {
            'repository': repo,
            'kept': sorted(kept_list),
            'deletions': [ {'digest': d, 'tags': sorted(list(info['tags'])), 'created': (info['created'].isoformat() if info['created'] else None)} for d, info in deletions_by_digest.items() ],
            'total_tags': len(tags),
        }

    def apply_policy(self, policy: Policy, simulate: bool = None) -> Dict:
        if simulate is None:
            simulate = policy.dry_run
        evaluation = self.evaluate_policy(policy)
        summary = {
            **evaluation,
            'simulate': simulate,
            'deleted_count': 0,
            'log_ids': [],
        }
        for detail in evaluation.get('details', []):
            repo = detail['repository']
            for deletion in detail['deletions']:
                digest = deletion['digest']
                tags = deletion['tags']
                success = False
                reason = ''
                if simulate:
                    success = True
                    reason = 'simulate'
                else:
                    try:
                        success = self.registry.delete_manifest(repo, digest)
                    except Exception as e:
                        success = False
                        reason = str(e)
                log = DeletionLog(
                    policy_id=policy.id,
                    repository=repo,
                    tag=','.join(tags),
                    digest=digest,
                    action='delete' if success else 'skip',
                    reason=reason,
                    success=success,
                    dry_run=simulate,
                )
                db.session.add(log)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                summary['log_ids'].append(log.id)
                if success:
                    summary['deleted_count'] += 1
        return summary


from datetime import datetime
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, abort
from models import db, Project, ApprovalRequest, ProjectMember, Role
from rbac import user_has_project_permission, available_roles

approvals_bp = Blueprint('approvals', __name__)


def login_required():
    if not g.user:
        abort(401)


@approvals_bp.route('/approvals')
def list_approvals():
    login_required()
    my_memberships = ProjectMember.query.filter_by(user_id=g.user.id).all()
    approvable_project_ids = [m.project_id for m in my_memberships if any(p.name == 'approve_requests' for p in m.role.permissions)]

    pending_for_me = []
    if approvable_project_ids:
        pending_for_me = ApprovalRequest.query.filter(
            ApprovalRequest.project_id.in_(approvable_project_ids),
            ApprovalRequest.status == 'PENDING'
        ).order_by(ApprovalRequest.created_at.desc()).all()

    my_requests = ApprovalRequest.query.filter_by(requester_id=g.user.id).order_by(ApprovalRequest.created_at.desc()).all()

    return render_template('approval_list.html', pending_for_me=pending_for_me, my_requests=my_requests)


@approvals_bp.route('/approvals/request/<int:project_id>', methods=['GET', 'POST'])
def request_access(project_id):
    login_required()
    project = Project.query.get_or_404(project_id)

    # If user already has edit/manage permissions, no need to request
    if user_has_project_permission(g.user, project, 'view_project') and not request.method == 'POST':
        # Show form anyway to request elevation
        pass

    if request.method == 'POST':
        role_id = request.form.get('role_id')
        reason = request.form.get('reason', '').strip()
        role = Role.query.get(role_id)
        if not role:
            flash('Invalid role selected', 'danger')
            return redirect(url_for('approvals.request_access', project_id=project.id))

        ar = ApprovalRequest(
            project_id=project.id,
            requester_id=g.user.id,
            target_user_id=g.user.id,
            requested_role_id=role.id,
            reason=reason,
            status='PENDING'
        )
        db.session.add(ar)
        db.session.commit()
        flash('Access request submitted', 'success')
        return redirect(url_for('approvals.list_approvals'))

    roles = available_roles()
    return render_template('request_access.html', project=project, roles=roles)


@approvals_bp.route('/approvals/<int:approval_id>/approve', methods=['POST'])
def approve_request(approval_id):
    login_required()
    ar = ApprovalRequest.query.get_or_404(approval_id)
    project = ar.project
    if not user_has_project_permission(g.user, project, 'approve_requests'):
        abort(403)
    if ar.status != 'PENDING':
        flash('Request already decided', 'warning')
        return redirect(url_for('approvals.list_approvals'))

    # Apply effect: if requested_role_id set, add/update membership
    if ar.requested_role_id:
        member = ProjectMember.query.filter_by(project_id=project.id, user_id=ar.target_user_id).first()
        if member:
            member.role_id = ar.requested_role_id
        else:
            db.session.add(ProjectMember(project_id=project.id, user_id=ar.target_user_id, role_id=ar.requested_role_id))

    ar.status = 'APPROVED'
    ar.decided_at = datetime.utcnow()
    ar.decided_by_id = g.user.id
    ar.decision_notes = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Request approved', 'success')
    return redirect(url_for('approvals.list_approvals'))


@approvals_bp.route('/approvals/<int:approval_id>/deny', methods=['POST'])
def deny_request(approval_id):
    login_required()
    ar = ApprovalRequest.query.get_or_404(approval_id)
    project = ar.project
    if not user_has_project_permission(g.user, project, 'approve_requests'):
        abort(403)
    if ar.status != 'PENDING':
        flash('Request already decided', 'warning')
        return redirect(url_for('approvals.list_approvals'))
    ar.status = 'DENIED'
    ar.decided_at = datetime.utcnow()
    ar.decided_by_id = g.user.id
    ar.decision_notes = request.form.get('notes', '').strip()
    db.session.commit()

    flash('Request denied', 'info')
    return redirect(url_for('approvals.list_approvals'))


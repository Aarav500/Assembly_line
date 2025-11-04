from flask import Blueprint, render_template, g, redirect, url_for, request, flash, abort
from models import db, Project, ProjectMember, Role, ApprovalRequest
from rbac import user_has_project_permission, requires_project_permission, available_roles

main_bp = Blueprint('main', __name__)


def login_required():
    if not g.user:
        abort(401)


@main_bp.route('/dashboard')
def dashboard():
    login_required()
    my_memberships = ProjectMember.query.filter_by(user_id=g.user.id).all()
    my_projects = [m.project for m in my_memberships]

    # Approvals pending my action across projects where I can approve
    approvable_project_ids = []
    for m in my_memberships:
        if any(p.name == 'approve_requests' for p in m.role.permissions):
            approvable_project_ids.append(m.project_id)
    pending_for_me = []
    if approvable_project_ids:
        pending_for_me = ApprovalRequest.query.filter(
            ApprovalRequest.project_id.in_(approvable_project_ids),
            ApprovalRequest.status == 'PENDING'
        ).order_by(ApprovalRequest.created_at.desc()).all()

    my_requests = ApprovalRequest.query.filter_by(requester_id=g.user.id).order_by(ApprovalRequest.created_at.desc()).all()

    return render_template('dashboard.html', my_projects=my_projects, pending_for_me=pending_for_me, my_requests=my_requests)


@main_bp.route('/projects')
def projects():
    login_required()
    projects = Project.query.order_by(Project.name.asc()).all()
    return render_template('projects.html', projects=projects)


@main_bp.route('/projects/<int:project_id>')
def project_detail(project_id):
    login_required()
    project = Project.query.get_or_404(project_id)
    members = ProjectMember.query.filter_by(project_id=project.id).all()

    can_manage = user_has_project_permission(g.user, project, 'manage_members')

    # Check if user is a member at all
    is_member = any(m.user_id == g.user.id for m in members)

    roles = available_roles()
    return render_template('project_detail.html', project=project, members=members, can_manage=can_manage, is_member=is_member, roles=roles)


@main_bp.route('/projects/<int:project_id>/members/add', methods=['POST'])
@requires_project_permission('manage_members')
def add_member(project_id):
    project = Project.query.get_or_404(project_id)
    username = request.form.get('username', '').strip()
    role_id = request.form.get('role_id')
    if not username or not role_id:
        flash('Username and role are required', 'danger')
        return redirect(url_for('main.project_detail', project_id=project.id))
    from models import User
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('main.project_detail', project_id=project.id))
    if ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first():
        flash('User is already a member', 'warning')
        return redirect(url_for('main.project_detail', project_id=project.id))
    role = Role.query.get(role_id)
    if not role:
        flash('Invalid role', 'danger')
        return redirect(url_for('main.project_detail', project_id=project.id))
    pm = ProjectMember(project_id=project.id, user_id=user.id, role_id=role.id)
    db.session.add(pm)
    db.session.commit()
    flash('Member added', 'success')
    return redirect(url_for('main.project_detail', project_id=project.id))


@main_bp.route('/projects/<int:project_id>/members/<int:member_id>/update', methods=['POST'])
@requires_project_permission('manage_members')
def update_member_role(project_id, member_id):
    project = Project.query.get_or_404(project_id)
    member = ProjectMember.query.get_or_404(member_id)
    if member.project_id != project.id:
        abort(404)
    role_id = request.form.get('role_id')
    role = Role.query.get(role_id)
    if not role:
        flash('Invalid role', 'danger')
        return redirect(url_for('main.project_detail', project_id=project.id))
    member.role_id = role.id
    db.session.commit()
    flash('Member role updated', 'success')
    return redirect(url_for('main.project_detail', project_id=project.id))


@main_bp.route('/projects/<int:project_id>/members/<int:member_id>/remove', methods=['POST'])
@requires_project_permission('manage_members')
def remove_member(project_id, member_id):
    project = Project.query.get_or_404(project_id)
    member = ProjectMember.query.get_or_404(member_id)
    if member.project_id != project.id:
        abort(404)
    db.session.delete(member)
    db.session.commit()
    flash('Member removed', 'info')
    return redirect(url_for('main.project_detail', project_id=project.id))


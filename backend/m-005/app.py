import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date
from models import db, Project, TaskTemplate, Employee, ChecklistItem
from services.generator import generate_checklist_for_employee
import os


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///onboarding.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_if_empty()

    register_routes(app)
    return app


def seed_if_empty():
    if Project.query.count() == 0:
        proj = Project(name='Acme CRM', description='Customer Relationship Management rollout project')
        db.session.add(proj)
        db.session.flush()

        templates = [
            TaskTemplate(project_id=proj.id, title='Set up company email', description='Provision and log into company email account', due_offset_days=0, role_filter=None, order_index=1),
            TaskTemplate(project_id=proj.id, title='Sign NDA', description='Complete and submit NDA documentation', due_offset_days=0, role_filter=None, order_index=2),
            TaskTemplate(project_id=proj.id, title='Security training', description='Complete required security awareness training', due_offset_days=3, role_filter=None, order_index=3),
            TaskTemplate(project_id=proj.id, title='Repository access', description='Request and verify access to source repository', due_offset_days=1, role_filter='Engineer', order_index=4),
            TaskTemplate(project_id=proj.id, title='Set up dev environment', description='Install dependencies and run the app locally', due_offset_days=2, role_filter='Engineer', order_index=5),
            TaskTemplate(project_id=proj.id, title='Create JIRA account', description='Ensure access to issue tracker', due_offset_days=1, role_filter=None, order_index=6),
        ]
        db.session.add_all(templates)

        emp = Employee(name='Jane Doe', email='jane.doe@example.com', role='Engineer', project_id=proj.id, start_date=date.today())
        db.session.add(emp)
        db.session.commit()

        generate_checklist_for_employee(emp.id)


def register_routes(app: Flask):
    @app.route('/')
    def index():
        projects = Project.query.order_by(Project.created_at.desc()).all()
        employees = Employee.query.order_by(Employee.created_at.desc()).all()
        return render_template('index.html', projects=projects, employees=employees)

    @app.route('/projects/new', methods=['GET', 'POST'])
    def new_project():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            if not name:
                flash('Project name is required.', 'error')
                return render_template('project_form.html')
            proj = Project(name=name, description=description)
            db.session.add(proj)
            db.session.commit()
            flash('Project created.', 'success')
            return redirect(url_for('project_detail', project_id=proj.id))
        return render_template('project_form.html')

    @app.route('/projects/<int:project_id>')
    def project_detail(project_id):
        project = Project.query.get_or_404(project_id)
        templates = TaskTemplate.query.filter_by(project_id=project_id).order_by(TaskTemplate.order_index.asc(), TaskTemplate.id.asc()).all()
        return render_template('project_detail.html', project=project, templates=templates)

    @app.route('/projects/<int:project_id>/tasks/new', methods=['POST'])
    def add_task_template(project_id):
        project = Project.query.get_or_404(project_id)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        role_filter = request.form.get('role_filter', '').strip() or None
        try:
            due_offset_days = int(request.form.get('due_offset_days', '0').strip() or '0')
        except ValueError:
            flash('Due offset days must be an integer.', 'error')
            return redirect(url_for('project_detail', project_id=project.id))

        max_order = db.session.query(db.func.max(TaskTemplate.order_index)).filter_by(project_id=project.id).scalar() or 0
        tmpl = TaskTemplate(project_id=project.id, title=title, description=description, role_filter=role_filter, due_offset_days=due_offset_days, order_index=max_order + 1)
        db.session.add(tmpl)
        db.session.commit()
        flash('Task template added.', 'success')
        return redirect(url_for('project_detail', project_id=project.id))

    @app.route('/employees/new', methods=['GET', 'POST'])
    def new_employee():
        projects = Project.query.order_by(Project.name.asc()).all()
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            role = request.form.get('role', '').strip()
            start_date_str = request.form.get('start_date', '').strip()
            project_id = request.form.get('project_id')

            if not name or not email or not start_date_str or not project_id:
                flash('Name, email, start date, and project are required.', 'error')
                return render_template('employee_form.html', projects=projects)
            try:
                start_dt = date.fromisoformat(start_date_str)
            except ValueError:
                flash('Invalid start date format.', 'error')
                return render_template('employee_form.html', projects=projects)

            employee = Employee(name=name, email=email, role=role or None, start_date=start_dt, project_id=int(project_id))
            db.session.add(employee)
            db.session.commit()

            generate_checklist_for_employee(employee.id)

            flash('Employee created and checklist generated.', 'success')
            return redirect(url_for('employee_detail', employee_id=employee.id))
        return render_template('employee_form.html', projects=projects, today=date.today())

    @app.route('/employees/<int:employee_id>')
    def employee_detail(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        items = ChecklistItem.query.filter_by(employee_id=employee.id).order_by(ChecklistItem.completed.asc(), ChecklistItem.sort_order.asc(), ChecklistItem.id.asc()).all()
        return render_template('employee_detail.html', employee=employee, items=items)

    @app.route('/employees/<int:employee_id>/regenerate', methods=['POST'])
    def employee_regenerate(employee_id):
        generate_checklist_for_employee(employee_id)
        flash('Checklist updated with any new template items.', 'success')
        return redirect(url_for('employee_detail', employee_id=employee_id))

    @app.route('/checklist/<int:item_id>/toggle', methods=['POST'])
    def toggle_checklist_item(item_id):
        item = ChecklistItem.query.get_or_404(item_id)
        item.completed = not item.completed
        db.session.commit()
        flash('Checklist item updated.', 'success')
        next_url = request.args.get('next') or url_for('employee_detail', employee_id=item.employee_id)
        return redirect(next_url)


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)



@app.route('/checklists', methods=['POST'])
def _auto_stub_checklists():
    return 'Auto-generated stub for /checklists', 200

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    task_templates = db.relationship('TaskTemplate', backref='project', lazy=True, cascade='all, delete-orphan')
    employees = db.relationship('Employee', backref='project', lazy=True)

    def __repr__(self):
        return f'<Project {self.id} {self.name}>'


class TaskTemplate(db.Model):
    __tablename__ = 'task_templates'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    due_offset_days = db.Column(db.Integer, default=0, nullable=False)
    role_filter = db.Column(db.String(100))  # if set, only applies to employees with matching role
    order_index = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f'<TaskTemplate {self.id} {self.title}>'


class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(100))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    checklist_items = db.relationship('ChecklistItem', backref='employee', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Employee {self.id} {self.name}>'


class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('task_templates.id'))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    template = db.relationship('TaskTemplate')

    def __repr__(self):
        return f'<ChecklistItem {self.id} emp={self.employee_id} {self.title}>'


from datetime import timedelta
from models import db, Employee, TaskTemplate, ChecklistItem


def generate_checklist_for_employee(employee_id: int):
    employee = Employee.query.get_or_404(employee_id)

    templates = TaskTemplate.query.filter_by(project_id=employee.project_id).order_by(TaskTemplate.order_index.asc()).all()

    existing_by_template = {}
    for item in ChecklistItem.query.filter_by(employee_id=employee.id).all():
        if item.template_id:
            existing_by_template[item.template_id] = item

    new_items = []
    next_sort = (
        db.session.query(db.func.max(ChecklistItem.sort_order))
        .filter_by(employee_id=employee.id)
        .scalar()
        or 0
    )

    for tmpl in templates:
        if tmpl.role_filter and employee.role and tmpl.role_filter.lower() != employee.role.lower():
            continue
        if tmpl.role_filter and not employee.role:
            # If template is role-specific but employee has no role, skip
            continue
        if tmpl.id in existing_by_template:
            continue

        due_date = employee.start_date + timedelta(days=tmpl.due_offset_days or 0)
        next_sort += 1
        item = ChecklistItem(
            employee_id=employee.id,
            template_id=tmpl.id,
            title=tmpl.title,
            description=tmpl.description,
            due_date=due_date,
            completed=False,
            sort_order=next_sort,
        )
        new_items.append(item)

    if new_items:
        db.session.add_all(new_items)
        db.session.commit()
    return new_items


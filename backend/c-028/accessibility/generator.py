import re


def generate_form_spec():
    return [
        {
            "id": "name",
            "name": "name",
            "type": "text",
            "label": "Full name",
            "required": True,
            "placeholder": "Ada Lovelace",
            "hint": "Enter your first and last name.",
            "autocomplete": "name",
            "max_length": 100,
        },
        {
            "id": "email",
            "name": "email",
            "type": "email",
            "label": "Email address",
            "required": True,
            "placeholder": "ada@example.com",
            "hint": "We'll use this to contact you.",
            "autocomplete": "email",
        },
        {
            "id": "age",
            "name": "age",
            "type": "number",
            "label": "Age",
            "required": True,
            "placeholder": "e.g., 34",
            "hint": "You must be at least 13 years old.",
            "min": 13,
            "max": 120,
            "inputmode": "numeric",
        },
        {
            "id": "contact_method",
            "name": "contact_method",
            "type": "radio",
            "label": "Preferred contact method",
            "required": True,
            "hint": "Choose how we should reach you.",
            "options": [
                {"value": "email", "label": "Email"},
                {"value": "phone", "label": "Phone"},
            ],
        },
        {
            "id": "newsletter",
            "name": "newsletter",
            "type": "checkbox",
            "label": "Subscribe to our accessibility newsletter",
            "required": False,
            "hint": "Monthly, no spam.",
            "value": "yes",
        },
        {
            "id": "message",
            "name": "message",
            "type": "textarea",
            "label": "Message",
            "required": True,
            "placeholder": "How can we help?",
            "hint": "Provide at least 10 characters.",
            "rows": 5,
            "max_length": 1000,
        },
    ]


def validate_form(form):
    errors = {}

    name = (form.get("name") or "").strip()
    if not name:
        errors["name"] = "Enter your full name."
    elif len(name) > 100:
        errors["name"] = "Name must be 100 characters or fewer."

    email = (form.get("email") or "").strip()
    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    if not email:
        errors["email"] = "Enter your email address."
    elif not email_re.match(email):
        errors["email"] = "Enter a valid email address."

    age_val = form.get("age")
    try:
        age = int(age_val)
        if age < 13:
            errors["age"] = "You must be at least 13 years old."
        elif age > 120:
            errors["age"] = "Enter a realistic age."
    except (TypeError, ValueError):
        errors["age"] = "Enter your age as a number."

    contact_method = form.get("contact_method")
    if contact_method not in {"email", "phone"}:
        errors["contact_method"] = "Choose a contact method."

    message = (form.get("message") or "").strip()
    if not message:
        errors["message"] = "Enter a message."
    elif len(message) < 10:
        errors["message"] = "Message must be at least 10 characters."

    return errors


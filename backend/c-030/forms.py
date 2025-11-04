from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, Regexp


class SubmitForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[
            DataRequired(message="Name is required."),
            Length(min=1, max=50),
            Regexp(r"^[\w\s\-\.'’]+$", message="Invalid characters in name."),
        ],
        filters=[lambda x: x.strip() if isinstance(x, str) else x],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(message="Email is required."), Email(), Length(min=1, max=120)],
        filters=[lambda x: x.strip().lower() if isinstance(x, str) else x],
    )
    comment = TextAreaField(
        "Comment",
        validators=[DataRequired(message="Comment is required."), Length(min=1, max=1000)],
        filters=[lambda x: x.strip() if isinstance(x, str) else x],
    )


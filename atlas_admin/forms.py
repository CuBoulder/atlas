from wtforms import Form, StringField, validators


class instanceSearchForm(Form):
    path = StringField('Path (contains)', [validators.Length(min=2, max=25)])

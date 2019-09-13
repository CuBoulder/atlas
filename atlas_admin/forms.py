from wtforms import Form, StringField, validators


class instanceSearchForm(Form):
    path = StringField('Path (contains)', [validators.Length(min=3, max=25)])

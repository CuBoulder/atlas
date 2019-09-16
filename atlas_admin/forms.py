from wtforms import Form, StringField, SelectField, validators


class searchForm(Form):
    query = StringField('Query', [validators.Length(min=1, max=50)])
    query_type = SelectField(u'Query type', choices=[(
        'path', 'Path (contains)'), ('username', 'User - Identikey'), ('email_address', 'User - Email')])

# Distant Life

A virtual pet site mixed with learning languages.

## Development

```sh
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=application
export FLASK_ENV=development # enable autoreload
```

```sh
brew install redis
# redis-cli shutdown
```

## Running

```sh
redis-server (one terminal)
flask run (another terminal)
```

## Translations

Get translation keys:

```python
pybabel extract -F babel.cfg -o messages.pot --input-dirs=.
# pybabel init -i messages.pot -d translations -l en # for init only
# pybabel init -i messages.pot -d translations -l he
pybabel update -i messages.pot -d translations -l en
pybabel update -i messages.pot -d translations -l he
```

After translating keys in translations folder compile .mo files:

```python
pybabel compile -d translations
```

Usage in templates with `_('Word')` or `gettext('Word')`:

```html
<h2>{{ _('Free Trial') }}</h2>
<input type="submit" value="{{ gettext('Sign up') }}"/>
```


Visit http://127.0.0.1:5000/

## Resources 

- [Front-end styling and development](https://virtual.github.io/fed-projects/04) | [GitHub Repo](https://github.com/virtual/fed-projects)
- [Figma design](https://www.figma.com/file/6ckmGH0eDFj1956hPH8n0V/DistantLife-final-CS50x?node-id=6%3A2860)

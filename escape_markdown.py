import re


def escape_markdown(text):
    escape_chars = r"()[]{}-_*.!"
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', text)

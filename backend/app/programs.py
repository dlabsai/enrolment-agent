# TODO: add better fake programs

_programs_text = """Teaching English Language Learners Graduate Certificate
Business Administration, BS
Cybersecurity, BS
Cybersecurity, MS
Digital Marketing, BS
Digital Marketing, MS
Graphic Design, BFA
Artificial Intelligence, BS
Artificial Intelligence, MS
Public Health, BS
Public Health, MPH
Business Administration, MBA
Software Engineering, BS
Software Engineering, MS"""


def _get_programs() -> list[str]:
    lines = _programs_text.splitlines()
    return list(dict.fromkeys([p.strip() for p in lines if p.strip()]))


PROGRAMS = _get_programs()

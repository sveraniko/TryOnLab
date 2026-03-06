from app.bot.services.parser import parse_measurements_text


def test_parse_measurements_text_pairs() -> None:
    parsed = parse_measurements_text('рост=176, грудь=96, талия=82')
    assert parsed == {'height_cm': 176, 'chest_cm': 96, 'waist_cm': 82}


def test_parse_measurements_text_json() -> None:
    parsed = parse_measurements_text('{"chest_cm": 96, "waist_cm": 82}')
    assert parsed == {'chest_cm': 96, 'waist_cm': 82}

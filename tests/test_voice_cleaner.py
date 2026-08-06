import pytest
from voice.cleaner import clean_text_for_speech


def test_clean_text_urls_and_markdown():
    raw = "Check out [FastAPI](https://fastapi.tiangolo.com) at www.fastapi.org for docs!"
    cleaned = clean_text_for_speech(raw)
    assert "https://" not in cleaned
    assert "www." not in cleaned
    assert "FastAPI" in cleaned
    assert cleaned == "Check out FastAPI at for docs!"


def test_clean_text_weather_formatting():
    raw = "The current weather in New York, United States is 28.5°C (83.3°F), clear sky. Source: open-meteo.com Confidence: High"
    cleaned = clean_text_for_speech(raw)
    assert "28.5 degrees Celsius" in cleaned
    assert "83.3 degrees Fahrenheit" in cleaned
    assert "Source:" not in cleaned
    assert "Confidence:" not in cleaned
    assert "open-meteo.com" not in cleaned


def test_clean_text_slashes_and_punctuation():
    raw = "Temperature / Humidity: 24°C... \\ Status: OK"
    cleaned = clean_text_for_speech(raw)
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert "..." not in cleaned
    assert "24 degrees Celsius" in cleaned

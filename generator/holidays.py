"""Holiday dates and captions for the art in the empty bottom-right corner of the screen.

holiday(date) names the holiday that falls on a date (or None). render.py draws that
holiday's picture (generator/holiday_art/<key>.png, OpenMoji, made by make_holiday_art.py)
on any screen whose forecast day is the holiday - so it shows on the "tomorrow" picture
the evening before and on the "today" picture on the day - but only where it fits
without touching any text.
"""
from datetime import date, timedelta


# ------------------------------------------------------------------ dates
def _nth_weekday(year, month, weekday, n):   # weekday: Mon=0; n=-1 = last
    if n > 0:
        d = date(year, month, 1)
        d += timedelta((weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta((d.weekday() - weekday) % 7)


def easter(year):   # Anonymous Gregorian algorithm
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def holidays(year):
    """{date: key} for one year."""
    return {
        date(year, 1, 1): "new_year",
        date(year, 2, 14): "valentine",
        date(year, 3, 17): "st_patrick",
        easter(year): "easter",
        date(year, 7, 4): "july4",
        date(year, 10, 31): "halloween",
        _nth_weekday(year, 11, 3, 4): "thanksgiving",
        date(year, 12, 25): "christmas",
    }


def holiday(day):
    """Key of the holiday on `day` (a date or 'YYYY-MM-DD'), or None."""
    if isinstance(day, str):
        day = date.fromisoformat(day)
    return holidays(day.year).get(day)


CAPTION = {
    "new_year": "Happy New Year",
    "valentine": "Happy Valentine's Day",
    "st_patrick": "Happy St. Patrick's Day",
    "easter": "Happy Easter",
    "july4": "Happy 4th of July",
    "halloween": "Happy Halloween",
    "thanksgiving": "Happy Thanksgiving",
    "christmas": "Merry Christmas",
}

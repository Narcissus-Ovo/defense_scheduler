"""Bounded, explicit date/time normalization used by import and scheduling."""
import re
import unicodedata
from datetime import datetime, timedelta

DATE = r'\d{4}-\d{1,2}-\d{1,2}'
CLOCK = r'\d{1,2}:\d{2}(?::00)?'


def normalize_text(value):
    text = unicodedata.normalize('NFKC', str(value)).replace('\xa0', ' ')
    for separator in ('—', '–', '～', '~', '－'):
        text = text.replace(separator, '-')
    text = re.sub(r'(\d{4})[年/.](\d{1,2})[月/.](\d{1,2})日?', r'\1-\2-\3', text)
    return text.strip()


def supply_explicit_year(value, year):
    """Fill missing years only when the user explicitly supplies an import year."""
    text = normalize_text(value)
    if not year:
        return text
    if not re.fullmatch(r'\d{4}', str(year)) or not 1900 <= int(year) <= 2100:
        raise ValueError('补全年份必须为 1900～2100 之间的四位年份')
    return re.sub(r'(?<![\d:\-])(\d{1,2})(?:月|/|-)(\d{1,2})日?(?![\d:])',
                  lambda match: f'{year}-{match[1]}-{match[2]}', text)


def expand_absolute_entry(value):
    """Return canonical daily intervals, or None for an unsupported/invalid entry.

    A date range followed by clocks means the same clock interval on each date,
    not continuous overnight availability. Expansion is limited to 366 days.
    """
    text = normalize_text(value)
    text = re.sub(r'\(每1天\)$', '', text).strip()
    match = re.fullmatch(
        rf'(?P<first>{DATE})(?:\s*(?:至|到|-)\s*(?P<last>{DATE}))?'
        rf'[\s,，]*(?P<start>{CLOCK})\s*(?:至|到|-)\s*(?P<end>{CLOCK})', text)
    if not match:
        period = re.fullmatch(rf'({DATE})\s*(上午|下午|全天|晚上)', text)
        if not period:
            return None
        from ..recurring_time import PERIOD_CLOCK_RANGES
        start, end = PERIOD_CLOCK_RANGES[period[2]]
        return expand_absolute_entry(f'{period[1]} {start}-{end}')
    try:
        first = datetime.strptime(match['first'], '%Y-%m-%d').date()
        last = datetime.strptime(match['last'] or match['first'], '%Y-%m-%d').date()
        start = datetime.strptime(':'.join(match['start'].split(':')[:2]), '%H:%M').strftime('%H:%M')
        end = datetime.strptime(':'.join(match['end'].split(':')[:2]), '%H:%M').strftime('%H:%M')
    except ValueError:
        return None
    count = (last - first).days + 1
    if not 1 <= count <= 366 or start >= end:
        return None
    return [f'{(first + timedelta(days=offset)).isoformat()} {start}-{end}' for offset in range(count)]


def combine_date_and_periods(date_value, clock_value):
    """Convert class periods into contiguous clock blocks, preserving lunch gaps."""
    from ..timetable import SINGLE_PERIOD_TIMES
    date_text = normalize_text(date_value)
    clock_text = normalize_text(clock_value)
    match = re.fullmatch(r'第\s*(\d+)\s*节\s*(?:-|至|到)\s*第?\s*(\d+)\s*节', clock_text)
    if not match:
        return f'{date_text} {clock_text}'
    first, last = map(int, match.groups())
    if first > last or any(number not in SINGLE_PERIOD_TIMES for number in range(first, last + 1)):
        return f'{date_text} {clock_text}'
    blocks = []
    for number in range(first, last + 1):
        start, end = SINGLE_PERIOD_TIMES[number]
        if blocks and start <= blocks[-1][1]:
            blocks[-1][1] = max(end, blocks[-1][1])
        else:
            blocks.append([start, end])
    return ','.join(f'{date_text} {start}-{end}' for start, end in blocks)

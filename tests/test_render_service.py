from app.services.render_service import _format_watermark_date


def test_format_watermark_date_kst_offset():
    result = _format_watermark_date("2026-07-10T14:32:00+09:00")
    assert result == "7/10 14:32"


def test_format_watermark_date_single_digit_padding():
    result = _format_watermark_date("2026-01-05T09:05:00+09:00")
    assert result == "1/5 09:05"

from app.store.render_sequence import RenderSequence


def test_increments_within_same_day():
    seq = RenderSequence()
    seq._date_str = "20260718"
    seq._counter = 0

    date1, num1 = seq.next()
    date2, num2 = seq.next()

    assert date1 == date2 == "20260718"
    assert num1 == "000001"
    assert num2 == "000002"


def test_resets_on_new_day():
    seq = RenderSequence()
    seq._date_str = "20260717"
    seq._counter = 41

    date_str, num = seq.next()

    assert num == "000001"
    assert date_str != "20260717"

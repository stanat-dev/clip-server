import threading
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


class RenderSequence:
    """날짜별로 000001부터 증가하고 자정(KST)에 초기화되는 렌더 결과물 번호 채번기."""

    def __init__(self):
        self._lock = threading.Lock()
        self._date_str = ""
        self._counter = 0

    def next(self) -> tuple[str, str]:
        today = datetime.now(KST).strftime("%Y%m%d")
        with self._lock:
            if today != self._date_str:
                self._date_str = today
                self._counter = 0
            self._counter += 1
            seq = f"{self._counter:06d}"
        return today, seq


render_sequence = RenderSequence()

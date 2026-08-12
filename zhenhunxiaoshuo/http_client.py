import time
import requests

class HttpClient:
    def __init__(self, timeout=30, retries=3, delay=1.0, user_agent=None):
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or "Mozilla/5.0 (compatible; FominhaDeNovel/1.0)"
        })

    def get_text(self, url: str) -> str:
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding
                if self.delay:
                    time.sleep(self.delay)
                return response.text
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(attempt * 2, 5))
        raise RuntimeError(f"Falha ao baixar {url}: {last_error}")

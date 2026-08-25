from __future__ import annotations

import argparse
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".pmtiles": "application/vnd.pmtiles",
    }

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        try:
            source = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        stat = os.fstat(source.fileno())
        size = stat.st_size
        start = 0
        end = size - 1
        status = 200

        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                source.close()
                self.send_error(416, "Invalid byte range")
                return None

            start_text, end_text = match.groups()
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else end
            elif end_text:
                suffix_length = int(end_text)
                start = max(0, size - suffix_length)

            end = min(end, size - 1)
            if start < 0 or start > end or start >= size:
                source.close()
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return None
            status = 206

        self.send_response(status)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        source.seek(start)
        self._remaining_bytes = end - start + 1
        return source

    def copyfile(self, source, outputfile) -> None:
        remaining = getattr(self, "_remaining_bytes", None)
        if remaining is None:
            return super().copyfile(source, outputfile)

        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local PMTiles demo with byte-range support.")
    parser.add_argument("--port", type=int, default=5500)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), RangeRequestHandler)
    print(f"Serving on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

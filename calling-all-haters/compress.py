from functools import wraps
from gzip import GzipFile
from io import BytesIO
import inspect

from quart import (request, current_app, make_response)
import htmlmin


class Compress:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.after_request(self.after_request)

    async def after_request(self, response):
        app = self.app or current_app
        accept_encoding = request.headers.get("Accept-Encoding", "")

        if (not ("gzip" in accept_encoding.lower() or "br" in accept_encoding.lower()) or "Content-Encoding" in response.headers or (response.content_length is not None and response.content_length < 500)):
            return response
        response.direct_passthrough = False

        gzip_content = await self.compress(app, response)
        response.set_data(gzip_content)

        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = response.content_length

        vary = response.headers.get("Vary")
        if vary:
            if "accept-encoding" not in vary.lower():
                response.headers["Vary"] = "{}, Accept-Encoding".format(vary)
        else:
            response.headers["Vary"] = "Accept-Encoding"

        return response

    async def compress(self, app, response):
        gzip_buffer = BytesIO()
        accept_encoding = request.headers.get("Accept-Encoding", "")

        if inspect.iscoroutinefunction(response.get_data):
            data = await response.get_data()
        else:
            data = response.get_data()

        if response.mimetype not in ["application/octet-stream", "application/javascript", "application/json"] and "image" not in response.mimetype:
            data = htmlmin.minify(data.decode(), remove_empty_space=True, reduce_boolean_attributes=True, convert_charrefs=True, remove_comments=True).encode("utf-8")

        if "gzip" in accept_encoding:
            with GzipFile(mode="wb", compresslevel=6, fileobj=gzip_buffer) as gzip_file:
                gzip_file.write(data)
            return gzip_buffer.getvalue()


_compress = Compress()


def compress_response():
    def wrapper(f):
        @wraps(f)
        async def compress(*args, **kwargs):
            _response = await f(*args, **kwargs) if inspect.iscoroutinefunction(f) else f(*args, **kwargs)
            return await _compress.after_request(await make_response(_response))
        return compress
    return wrapper

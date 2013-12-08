import BaseHTTPServer
import requests
import os
import threading
import socket
from SocketServer import ThreadingMixIn



class VideoHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        print "received request : " + self.raw_requestline
        requestline = "http://192.168.1.12:8080/videofeed"
        print "send request: ", requestline

        print threading.currentThread().getName()
        response = requests.get(requestline, stream=True)
        self.send_response(200)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        for chunk in response.iter_content(1000):
            self.wfile.write(chunk)
            self.wfile.flush()
        return True

    def handle_one_request(self):
        """Handle a single HTTP request.

        You normally don't need to override this method; see the class
        __doc__ string for information on how to handle specific HTTP
        commands such as GET and POST.

        """
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = 1
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return
            mname = 'do_' + self.command
            if not hasattr(self, mname):
                self.send_error(501, "Unsupported method (%r)" % self.command)
                return
            method = getattr(self, mname)
            do_not_flush = method()
            if (not do_not_flush):
                self.wfile.flush() #actually send the response if not already done.
        except socket.timeout, e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = 1
            return


class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass


def main():
    server = ThreadedHTTPServer( ('',8080),VideoHandler )
    server.serve_forever()

if ("__main__" == __name__):
    main()

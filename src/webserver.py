import BaseHTTPServer
import requests
import os
import threading

class VideoThread(threading.Thread):
    def __init__(self, iRequestLine, iVideoHandler):
        threading.Thread.__init__(self)
        self.requestLine = iRequestline
        self.videoHandler = iVideoHandler

    def run(self):
        response = requests.get(self.requestLine, stream=True)
        self.videoHandler.send_response(200)
        for key, value in response.headers.items():
            self.videoHandler.send_header(key, value)
        self.videoHandler.end_headers()
        for chunk in response.iter_content(1000):
            self.videoHandler.wfile.write(chunk)
            self.videoHandler.wfile.flush()

class VideoHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        print self.raw_requestline
        #self.headers["host"] = "192.168.1.19:8080"
        #for key, value in self.headers.items():
            #print key, "->", value
        #requestline = "http://google.fr"
        requestline = "http://192.168.1.19:8080/videofeed"
        print "send request:", requestline
        thread1 = VideoThread(requestline, self)
        thread1.start()
        print "done"
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

def main():
    server = BaseHTTPServer.HTTPServer( ('',8080),VideoHandler )
    server.serve_forever()

if ("__main__" == __name__):
    main()

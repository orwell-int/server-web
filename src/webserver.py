import BaseHTTPServer
import requests
import os
import threading
import socket
import argparse
from SocketServer import ThreadingMixIn



class VideoHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        print "received request : " + self.raw_requestline
        requestline = "http://{ip}:8080/videofeed".format(ip=VideoHandler.feed_ip);
        #requestline = "http://easyhtml5video.com/images/happyfit2.mp4"

        print threading.currentThread().getName()
        response = requests.get(requestline, stream=True)
        self.send_response(200)
        for key, value in response.headers.items():
            print key, value
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
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--ip', action='store', dest='videofeed_ip', help='the IP adresse of the videofeed', default='192.198.1.1')
    argparser.add_argument('-p', action='store', dest='port', type=int, help='the port on which this server retransmits', default='9100')
    arguments = argparser.parse_args()

    VideoHandler.feed_ip = arguments.videofeed_ip
    server = ThreadedHTTPServer( ('', arguments.port), VideoHandler )
    server.serve_forever()

if ("__main__" == __name__):
    main()

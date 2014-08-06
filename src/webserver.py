import os
import BaseHTTPServer
import requests
import threading
import socket
import argparse
from SocketServer import ThreadingMixIn
import logging


class VideoHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        logging.info("received request : " + self.raw_requestline)
        requestline = VideoHandler.url
        #requestline = "http://easyhtml5video.com/images/happyfit2.mp4"

        logging.debug(threading.currentThread().getName())
        response = requests.get(requestline, stream=True)
        self.send_response(200)
        for key, value in response.headers.items():
            logging.debug(key + " " + value)
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
                #actually send the response if not already done.
                self.wfile.flush()
        except socket.timeout, e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = 1
            return


class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '-u',
        action='store',
        dest='videofeed_url',
        help='the url of the videofeed',
        default='http://192.198.1.1:8080/videofeed')
    argparser.add_argument(
        '-p',
        action='store',
        dest='output_port',
        type=int,
        help='the port on which this server retransmits',
        default='9100')
    argparser.add_argument(
        '--pid-file',
        action='store',
        dest='pid_file',
        help='the itmp file in which we store the pids of the webservers',
        default=None)
    arguments = argparser.parse_args()

    if (arguments.pid_file is not None):
        logging.basicConfig(
            filename=arguments.pid_file + '.log',
            level=logging.DEBUG)
        with open(arguments.pid_file, "w") as pidfile:
            pidfile.write(str(os.getpid()))
    VideoHandler.url = arguments.videofeed_url
    server = ThreadedHTTPServer(('', arguments.output_port), VideoHandler)
    logging.info("Start server")
    server.serve_forever()

if ("__main__" == __name__):
    main()

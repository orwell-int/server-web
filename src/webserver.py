import os
import BaseHTTPServer
import requests
import threading
import socket
import argparse
from SocketServer import ThreadingMixIn
import logging
import zmq


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
            if "content-type" == key:
                _, _, boundary = value.partition("boundary=")
            self.send_header(key, value)
        self.end_headers()

        image = ""
        self.dumped = False
        image_started = False
        for chunk in response.iter_content(1000):
            message = VideoHandler.socket.recv(zmq.NOBLOCK)
            if (message is not None):
                if "capture" == message:
                    capture = True

            if capture:
                index_chunk1 = chunk.find(boundary)
                if index_chunk1 != -1:
                    print "image starts at ", index_chunk1
                    if (image_started):
                        image += chunk[:index_chunk1]
                        image_started = False
                        self.dump_image(image)
                        capture = False
                    else:
                        index_chunk1 += len(boundary)
                        index_chunk2 = chunk.find(boundary, index_chunk1)
                        if index_chunk2 != -1:
                            image = chunk[index_chunk1:index_chunk2]
                            image_started = False
                            self.dump_image(image)
                            capture = False
                        else:
                            image_started = True
                            image += chunk[index_chunk1:]
                else:
                    if image_started:
                        image += chunk
            
            self.wfile.write(chunk)
            self.wfile.flush()
        return True

    def dump_image(self, image):
        if not self.dumped:
            index = 0
            for i in range(4):
                index = image.find("\r\n", index) + 2
            VideoHandler.socket.send(image[index:])
            self.dumped = True

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
        '-l',
        action='store',
        dest='listen_port',
        type=int,
        help='the port on which this server listens to instructions',
        default='9010')
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

    import zmq
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 1)
    socket.bind("tcp://*:%i" % (arguments.listen_port))
    # if we do not wait the first messages are lost
    import time
    time.sleep(0.6)
    if (arguments.pid_file is not None):
        logging.basicConfig(
            filename=arguments.pid_file + '.log',
            level=logging.DEBUG)
        with open(arguments.pid_file, "w") as pidfile:
            pidfile.write(str(os.getpid()))
    VideoHandler.url = arguments.videofeed_url
    VideoHandler.socket = socket
    server = ThreadedHTTPServer(('', arguments.output_port), VideoHandler)
    logging.info("Start server")
    server.serve_forever()

if ("__main__" == __name__):
    main()

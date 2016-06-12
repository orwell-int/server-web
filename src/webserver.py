import os
import BaseHTTPServer
import requests
import threading
import socket
import argparse
from SocketServer import ThreadingMixIn
import logging
import zmq
import time


class FakeResponse(object):
    def __init__(self, path):
        self._path = path
        self._stop = False
        directory = os.path.dirname(path)
        self._content = ""
        import json
        json_data = ""
        self._frames = []
        with open(self._path, 'rb') as data_file:
            json_data = data_file.read()
        data = json.loads(json_data)
        frame_separator = data["frame_separator"]
        for image in data["frames"]:
            print "read image from", image
            with open(os.path.join(directory, image), 'rb') as image_file:
                image_data = bytearray(image_file.read())
                #image_data = unicode(image_data, 'utf-8')
                frame = bytearray(b'--')
                frame += bytearray(frame_separator, 'utf-8')
                frame += bytearray(b'\r\n')
                frame += bytearray(b'Content-Type: image/jpeg\r\n\r\n')
                frame += image_data + bytearray(b'\r\n')
                self._frames.append(frame)
        self.headers = {key: value.format(frame_separator=frame_separator)
                        for key, value in data["headers"].items()}
        print "headers"
        print str(self.headers)
        self._image_index = 0
        self._index = 0
        #print "content-type =", self.headers["content-type"]
        self._image_count = len(self._frames)
        self._lengths = [len(image) for image in self._frames]
        #print "image count =", self._image_count

    def stop(self):
        self._stop = True

    def iter_content(self, count):
        wait = False
        while (not self._stop):
            buffer = bytearray()
            end = count + self._index
            if (end > self._lengths[self._image_index]):
                # here we reach the end of an image so we go to the end
                # and wait without filling completely the buffer
                buffer.extend(self._frames[self._image_index][self._index:])
                # switch to next image
                self._image_index = (self._image_index + 1) % self._image_count
                self._index = 0
                wait = True
            else:
                buffer = self._frames[self._image_index][self._index:end]
                self._index += count
            yield buffer
            if (wait):
                #print "next image"
                logging.debug("next image")
                time.sleep(0.5)
                wait = False


class GstResponse(object):
    def __init__(self, video_format):
        self._video_format = video_format
        assert(video_format in ('mp4', 'ogg', 'mkv', 'webm'))
        self._stop = False
        self.headers = {'Content-type': 'video/' + video_format}
        print "headers"
        print str(self.headers)

    def stop(self):
        self._stop = True

    def iter_content(self, count):
        import subprocess
        wait = False
        command = 'echo "--video boundary--" ;'
        if ('mp4' == self._video_format):
            command += 'gst-launch-1.0 -e -q videotestsrc is-live=true' \
                + ' ! video/x-raw, framerate=5/1, width=160, height=120' \
                + ' ! clockoverlay shaded-background=true font-desc="Sans 38"' \
                + ' ! videoconvert' \
                + ' ! x264enc' \
                + ' ! h264parse' \
                + ' ! mp4mux streamable=true fragment-duration=10 presentation-time=true' \
                + ' ! filesink location=/dev/stdout'
        elif ('ogg' == self._video_format):
            command += 'gst-launch-1.0 -e -q videotestsrc is-live=true' \
                + ' ! video/x-raw, framerate=5/1, width=1024, height=768' \
                + ' ! clockoverlay shaded-background=true font-desc="Sans 38"' \
                + ' ! theoraenc' \
                + ' ! oggmux max-delay=0' \
                + ' ! filesink location=/dev/stdout'
        elif ('mkv' == self._video_format):
            command += 'gst-launch-1.0 -e -q videotestsrc is-live=true' \
                + ' ! video/x-raw, framerate=5/1, width=1024, height=768' \
                + ' ! clockoverlay shaded-background=true font-desc="Sans 38"' \
                + ' ! videoconvert' \
                + ' ! x264enc' \
                + ' ! h264parse' \
                + ' ! matroskamux' \
                + ' ! filesink location=/dev/stdout'
        elif ('webm' == self._video_format):
            command += 'gst-launch-1.0 -e -q videotestsrc is-live=true' \
                + ' ! video/x-raw, framerate=5/1, width=1024, height=768' \
                + ' ! clockoverlay shaded-background=true font-desc="Sans 38"' \
                + ' ! videoconvert' \
                + ' ! vp8enc' \
                + ' ! webmmux' \
                + ' ! filesink location=/dev/stdout'
        process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                bufsize=-1,
                shell=True)
        print("starting polling loop.")
        while (not self._stop):
            # print "looping... "
            chars = process.stdout.read(2000)
            # print repr(chars)
            yield chars
            if (process.poll() is not None):
                self.stop()


def netstat():
    import subprocess
    command = ['netstat', '-l', '-p']
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    process.wait()
    logging.debug("command = " + ' '.join(command))
    logging.debug("stdout = " + process.stdout.read())
    logging.debug("stderr = " + process.stderr.read())


class VideoHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        #print "do_GET"
        logging.info("received request : " + self.raw_requestline)
        self._fake =  not VideoHandler.url.startswith('http')
        gst = False
        if (self._fake):
            print("start fake server")
            logging.info("start fake server")
            if (os.path.exists(VideoHandler.url)):
                self._response = FakeResponse(VideoHandler.url)
            else:
                self._response = GstResponse(VideoHandler.url)
                gst = True
        else:
            requestline = VideoHandler.url

            logging.debug(threading.currentThread().getName())
            logging.info("send request")
            self._response = requests.get(requestline, stream=True)
        self.send_response(200)
        for key, value in self._response.headers.items():
            logging.debug(key + " " + value)
            if "content-type" == key:
                _, _, boundary = value.partition("boundary=")
                boundary = bytearray(boundary, encoding='ascii')
            self.send_header(key, value)
        self.end_headers()

        self._image = bytearray()
        self._dumped = False
        self._image_started = False
        self._capture = False
        self._captured = 0

        message = None
        import datetime
        latest = datetime.datetime.now()
        previous = latest
        delta = datetime.timedelta(microseconds=1000 * 500)  # 0.5s
        logging.info("begin transmission of chunks")
        for chunk in self._response.iter_content(1000):
            latest = datetime.datetime.now()
            if (latest - previous > delta):
                logging.debug("still sending chunks ...")
                previous = latest
                if (VideoHandler.use_zmq):
                    try:
                        #logging.debug("socket.recv:")
                        message = VideoHandler.socket.recv(zmq.NOBLOCK)
                    except Exception as exc:
                        logging.warning("ZMQ: " + str(exc))
                        #netstat()
                        message = None
                if (message is not None):
                    logging.info("received zmq command: '%s'" % message)
                    try:
                        if "capture" == message:
                            self._capture = True
                            self._dumped = False
                        elif "ping" == message:
                            VideoHandler.socket.send("pong")
                        elif "status" == message:
                            VideoHandler.socket.send(
                                "captured = " + str(self._captured))
                        elif "stop" == message:
                            VideoHandler.socket.send("stopping")
                            logging.info("stopping")
                            break
                    except Exception as exc:
                        logging.warning("while sending:" + str(exc))

            if self._capture:
                logging.debug("chunk =" + repr(chunk[:20]))
                index_chunk1 = chunk.find(boundary)
                if index_chunk1 != -1:
                    if (self._image_started):
                        logging.debug("image ends (boundary found)")
                        self._image += chunk[:index_chunk1]
                        self._finalize_image()
                    else:
                        logging.debug("image starts at " + str(index_chunk1))
                        self._image_started = True
                        index_chunk1 += len(boundary)
                        index_chunk2 = chunk.find(boundary, index_chunk1)
                        if index_chunk2 != -1:
                            self._image = chunk[index_chunk1:index_chunk2]
                            self._finalize_image()
                        else:
                            self._image_started = True
                            self._image += chunk[index_chunk1:]
                else:
                    logging.debug("image continues (no boundary found)")
                    if self._image_started:
                        self._image += chunk

            self.wfile.write(chunk)
            self.wfile.flush()
        logging.info("end transmission of chunks")
        return True

    def _finalize_image(self):
        logging.debug("_finalize_image")
        self._image_started = False
        if not self._dumped:
            index = 0
            for i in range(4):
                index = self._image.find("\r\n", index) + 2
            VideoHandler.socket.send(self._image[index:])
            self._dumped = True
            logging.info("image sent")
            self._captured += 1
        self._capture = False

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
        except socket.error, e:
            if e.args[0] == 32:
                # broken pipe
                self._stop()
                return
            raise e

    def finish(self, *args, **kw):
        try:
            if not self.wfile.closed:
                self.wfile.flush()
                self.wfile.close()
        except socket.error:
            pass
        self.rfile.close()

    def _stop(self):
        if (self._fake):
            self._response.stop()


class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass


def dump_to_file(
        url,
        filename):
    logging.debug(threading.currentThread().getName())
    response = requests.get(url, stream=True)
    data = {}
    data["headers"] = dict(response.headers)
    for key, value in response.headers.items():
        logging.debug(key + " " + value)
        if "content-type" == key:
            _, _, boundary = value.partition("boundary=")

    content = ""
    filled = False
    image_started = False
    expected_images = 4

    for chunk in response.iter_content(1000):
        if (not image_started):
            index_chunk = chunk.find(boundary)
            if index_chunk != -1:
                content += chunk[index_chunk:]
                image_started = True
        else:
            content += chunk
        boundary_count = content.count(boundary)
        if (boundary_count > expected_images):
            content = boundary.join(
                content.split(boundary)[:expected_images])
            filled = True
            break
    #print "filled =", filled
    if (filled):
        with open(filename, "w") as writer:
            import json
            writer.write(json.dumps(data))
        with open(filename, "a") as writer:
            writer.write("\n")
            writer.write(content)


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
        '--no-zmq',
        action='store_true',
        help='Disable zmq socket when running the server.',
        default=False)
    argparser.add_argument(
        '--pid-file',
        action='store',
        dest='pid_file',
        help='the file in which we store the pid of the webserver',
        default=None)
    argparser.add_argument(
        '--dump-file',
        help='If set dump a few frames in the file as json,'
        ' to be used as a fake url.',
        default=None)
    arguments = argparser.parse_args()
    if (arguments.pid_file is not None):
        logging.basicConfig(
            filename=arguments.pid_file + '.log',
            level=logging.DEBUG)
        with open(arguments.pid_file, "w") as pidfile:
            pidfile.write(str(os.getpid()))

    VideoHandler.use_zmq = not arguments.no_zmq
    if (VideoHandler.use_zmq):
        import zmq
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.setsockopt(zmq.LINGER, 1)
        VideoHandler.socket = socket
        logging.info(
            "video server zmq bind on port " + str(arguments.listen_port))
        try:
            socket.bind("tcp://*:%i" % (arguments.listen_port))
        except Exception as exc:
            logging.error(exc)
            import sys
            netstat()
            sys.exit(-1)
        # if we do not wait the first messages are lost
        import time
        time.sleep(0.6)
    if (arguments.dump_file is not None):
        logging.info("dump to a file")
        dump_to_file(arguments.videofeed_url, arguments.dump_file)
    else:
        VideoHandler.url = arguments.videofeed_url
        server = ThreadedHTTPServer(('', arguments.output_port), VideoHandler)
        logging.info("Start server")
        server.serve_forever()

if ("__main__" == __name__):
    main()

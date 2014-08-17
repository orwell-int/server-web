import requests
import argparse
import datetime
import time
import zmq


def read(
        url,
        socket,
        delay):
    print "Send request to", url
    response = requests.get(url, stream=True)
    begin = datetime.datetime.now()
    end = begin + datetime.timedelta(seconds=delay)
    for chunk in response.iter_content(1000):
        try:
            print '(fake client)zmq?'
            message = socket.recv(zmq.NOBLOCK)
        except Exception as exc:
            print '(fake client)socket.recv:', exc
            message = None
        if (message is not None):
            print "received command '%s'" % message
            try:
                if ("ping" == message):
                    socket.send("pong")
                elif ("stop" == message):
                    socket.send("stopping")
                    break
            except Exception as exc:
                print '(fake client)socket.send:', exc
        time.sleep(0.1)
        if (datetime.datetime.now() > end):
            break
    print "(fake client)quit"


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '-u',
        action='store',
        dest='url',
        help='the url of the videofeed',
        default=None)
    argparser.add_argument(
        '--delay',
        '-d',
        action='store',
        type=int,
        help='Delay before the client exits (in seconds).',
        default=5)
    argparser.add_argument(
        '-l',
        action='store',
        dest='listen_port',
        type=int,
        help='the port on which this client listens to instructions',
        default='9020')
    arguments = argparser.parse_args()
    print "fake client arguments =", arguments
    if (arguments.url):
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.setsockopt(zmq.LINGER, 1)
        print "create REP socket on port", arguments.listen_port
        socket.bind("tcp://*:%i" % (arguments.listen_port))
        print "created REP socket on port", arguments.listen_port
        time.sleep(0.6)
        read(arguments.url, socket, arguments.delay)

if ("__main__" == __name__):
    main()

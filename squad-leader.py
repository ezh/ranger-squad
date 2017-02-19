# Copyright 2017 Alexey Aksenov. All rights reserved.
# Licensed under the Apache License, version 2.0:
# http://www.apache.org/licenses/LICENSE-2.0

import zmq
import random
import sys
import time
import pickle
import logging


class SquadLeader:
    topic = b'squad'
    poll_timeout = 1000

    def __init__(self):
        logging.info("Starting ranger squad leader")
        self.addressin = "ipc:///tmp/ranger-squad-reports.ipc"
        self.addressout = "ipc:///tmp/ranger-squad-commands.ipc"
        self.context = zmq.Context()
        self.socket_report = self.context.socket(zmq.DEALER)
        self.socket_command = self.context.socket(zmq.XPUB)

    def bind(self):
        logging.info("Listen squad reports at %s" % self.addressin)
        self.socket_report.bind(self.addressin)
        logging.info("Send squad commands via %s" % self.addressout)
        """
        ZMQ_XPUB_VERBOSE: provide all subscription messages on XPUB sockets
        Sets the XPUB socket behavior on new subscriptions and unsubscriptions.
        A value of 0 is the default and passes only new subscription messages to upstream.
        A value of 1 passes all subscription messages upstream.
        """
        self.socket_command.setsockopt(zmq.XPUB_VERBOSE, 1)
        self.socket_command.bind(self.addressout)

    def run(self):
        logging.info("Starting leader event loop")
        p = zmq.Poller()
        p.register(server.socket_report, zmq.POLLIN)
        p.register(server.socket_command, zmq.POLLIN)
        while True:
            try:
                # Wait for next request from client
                time.sleep(1)
                logging.info("Waiting for squad reports")
                data = self.socket_report.recv()
                l = pickle.loads(data)
                logging.info("""Received command "%s" from ranger %s""" % (l[0], l[1]))
                self.socket_command.send_multipart([self.topic, data])
            except KeyboardInterrupt as e:
                raise e
            except Exception as e:
                print("Got an exception, closing and restarting:", e)
                try:
                    self.socket_report.close()
                    self.socket_command.close()
                except:
                    print("Exception closing sockets, ignoring")
                try:
                    self.context.term()
                except:
                    print("Exception closing context, ignoring")
                time.sleep(1)
                self.context = zmq.Context()
                self.socket_report = self.context.socket(zmq.DEALER)
                self.socket_command = self.context.socket(zmq.XPUB)
                self.bind()

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
server = SquadLeader()
server.bind()
server.run()


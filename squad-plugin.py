# Copyright 2017 Alexey Aksenov. All rights reserved.
# Licensed under the Apache License, version 2.0:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Compatible with ranger 1.9.x
#
# This plugin makes the ranger a part of team

import os

import zmq
import pickle

import ranger
import ranger.core.actions as ra
import ranger.api.commands as rc
from ranger.container.file import File

from logging import getLogger

import time
import remote_pdb

try:
    import thread
except ImportError:
    import _thread as thread

LOG = getLogger(__name__)


class SquadClient:
    topic = b'squad'

    def __init__(self, fm: ranger.core.fm.FM):
        self.command = {}
        self.pid = os.getpid()
        self.fm = fm
        self.context = zmq.Context()
        self.address_reports = ["ipc:///tmp/ranger-squad-reports.ipc"]
        self.address_commands = ["ipc:///tmp/ranger-squad-commands.ipc"]
        self.socket_report = self.context.socket(zmq.DEALER)
        self.socket_command = self.context.socket(zmq.SUB)
        self.socket_command.setsockopt(zmq.SUBSCRIBE, self.topic)


    def connect(self):
        LOG.debug("Send reports to %s" % self.address_reports)
        for address in self.address_reports:
            self.socket_report.connect(address)
        LOG.debug("Listen commands at %s" % self.address_commands)
        for address in self.address_commands:
            self.socket_command.connect(address)
        thread.start_new_thread(self.listener, ())


    def listener(self):
        while(True):
            try:
                topic, data = self.socket_command.recv_multipart()
                command, pid, env, args = self.load(data)
                if (pid == self.pid):
                    LOG.debug('Leader confirmed command "%s"' % (command))
                    continue
                LOG.debug("""Receive command "%s" from ranger %s""" % (command, pid))
                self.command[command](pid, env, args)
            except Exception as ex:
                LOG.debug("Unable to read data from squad" + str(ex))

    def load(self, data):
        l = pickle.loads(data)
        command = l[0]
        pid = l[1]
        env = l[2]
        del l[0:3]
        return command, pid, env, l


    def set_socket_option(self, option, value):
        attr = getattr(zmq, option, None)
        if attr:
            self.socket_report.setsockopt(attr, value)
            self.socket_command.setsockopt(attr, value)


    def save(self, command, data):
        return pickle.dumps([command, self.pid, dict((k,os.environ[k]) for k in os.environ)] + data)


    def ranger_copy_get(self, pid, env, args):
        try:
            self.fm.copy_buffer = set(File(g) for g in args if os.path.exists(g))
            self.fm.ui.redraw_main_column()
        except Exception as ex:
            LOG.debug("Unable to process copy data from squad" + str(ex))

    def ranger_copy_send(self):
        try:
            self.socket_report.send(self.save('copy', [fobj.path for fobj in self.fm.copy_buffer]))
        except Exception as ex:
            LOG.debug("Unable to send copy data to squad" + str(ex))


client = SquadClient(ranger.fm)
# Set idle time, before sending keepalive probes
client.set_socket_option('TCP_KEEPALIVE', 1)
# Set max. number of keep alive probes, before tcp gives up
client.set_socket_option('TCP_KEEPALIVE_CNT', 3)
# Number of seconds between sending keepalives on an otherwise idle connection
client.set_socket_option('TCP_KEEPALIVE_IDLE', 5)
# Set keep alive interval probes
client.set_socket_option('TCP_KEEPALIVE_INTVL', 15)
client.connect()


def copy_SQUAD(mode='set', narg=None, dirarg=None):
    """:copy [mode=set]

    Copy the selected items.
    Modes are: 'set', 'add', 'remove'.
    """
    result = ra.Actions.copy(client.fm, mode, narg, dirarg)
    client.ranger_copy_send()
    return result

# Overwrite the old one
if 'copy' in ranger.fm.commands.commands:
    client.command['copy'] = client.ranger_copy_get
    ranger.fm.commands.commands['copy'] = rc._command_init(rc.command_function_factory(copy_SQUAD))


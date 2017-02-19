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
        self.original = {}
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
        self.leader_report(self.topic, self.pid, -1, 'iamhere', [])


    def leader_command(self):
        topic, data = self.socket_command.recv_multipart()
        l = pickle.loads(data)
        from_pid = l[0]
        to_pid = l[1]
        command = l[2]
        env = l[3]
        del l[0:4]
        return command, from_pid, to_pid, env, l


    def leader_report(self, topic, from_pid, to_pid, command, data):
        LOG.debug('Report to leader: subject "%s", destination: "%s"' % (command, to_pid))
        message = pickle.dumps([from_pid, to_pid, command, dict((k,os.environ[k]) for k in os.environ)] + data)
        self.socket_report.send_multipart([topic, message])


    def listener(self):
        while(True):
            try:
                command, from_pid, to_pid, env, args = self.leader_command()
                if (from_pid == self.pid):
                    LOG.debug('Leader confirmed command "%s"' % (command))
                    continue
                if (to_pid == 0 or to_pid == self.pid):
                    LOG.debug("""Receive command "%s" from trooper %s""" % (command, from_pid))
                    self.command[command](from_pid, env, args)
            except Exception as ex:
                LOG.debug("Unable to read data from squad" + str(ex))


    def ranger_bookmark_get(self, pid, env, args):
        try:
            bookmarks = dict((k,File(v)) for (k,v) in args[0].items() if os.path.exists(v))
            self.fm.bookmarks._set_dict(bookmarks, original=bookmarks)
            self.fm.ui.redraw_main_column()
        except Exception as ex:
            LOG.debug("""Unable to process "bookmark" command from squad: """ + str(ex))


    def ranger_bookmark_send(self):
        try:
            self.leader_report(self.topic, self.pid, 0, 'bookmark', [dict((k,v.path) for (k,v) in self.fm.bookmarks.dct.items())])
        except Exception as ex:
            LOG.debug("""Unable to send "bookmark" report to squad: """ + str(ex))


    def ranger_copy_get(self, pid, env, args):
        try:
            self.fm.copy_buffer = set(File(g) for g in args if os.path.exists(g))
            self.fm.ui.redraw_main_column()
        except Exception as ex:
            LOG.debug("""Unable to process "copy" command from squad: """ + str(ex))


    def ranger_copy_send(self):
        try:
            self.leader_report(self.topic, self.pid, 0, 'copy', [fobj.path for fobj in self.fm.copy_buffer])
        except Exception as ex:
            LOG.debug("""Unable to send "copy" report to squad: """ + str(ex))


    def ranger_tag_get(self, pid, env, args):
        try:
            self.fm.tags.tags = args[0]
            self.fm.ui.redraw_main_column()
        except Exception as ex:
            LOG.debug("""Unable to process "tag" command from squad: """ + str(ex))


    def ranger_tag_send(self):
        try:
            self.leader_report(self.topic, self.pid, 0, 'tag', [self.fm.tags.tags])
        except Exception as ex:
            LOG.debug("""Unable to send "tag" report to squad: """ + str(ex))


    def set_socket_option(self, option, value):
        attr = getattr(zmq, option, None)
        if attr:
            self.socket_report.setsockopt(attr, value)
            self.socket_command.setsockopt(attr, value)



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


def copy_SQUAD(self, mode='set', narg=None, dirarg=None):
    """:copy [mode=set]

    Copy the selected items.
    Modes are: 'set', 'add', 'remove'.
    """
    result = client.original['copy'](self, mode, narg, dirarg)
    client.ranger_copy_send()
    return result

def copy_SQUAD_cmd(mode='set', narg=None, dirarg=None):
    """:copy [mode=set]

    Copy the selected items.
    Modes are: 'set', 'add', 'remove'.
    """
    result = client.original['copy'](client.fm, mode, narg, dirarg)
    client.ranger_copy_send()
    return result


# Overwrite the old one
if 'copy' in ranger.fm.commands.commands:
    LOG.debug("Share copy command")
    client.original['copy'] = ra.Actions.copy
    client.command['copy'] = client.ranger_copy_get
    ranger.fm.commands.commands['copy'] = rc._command_init(rc.command_function_factory(copy_SQUAD_cmd))
    ra.Actions.copy = copy_SQUAD


def tag_SQUAD(self, paths=None, value=None, movedown=None, tag=None):
    """:tag_toggle <character>

    Toggle a tag <character>.
    """
    result = client.original['tag'](self, paths, value, movedown, tag)
    client.ranger_tag_send()
    return result

def tag_SQUAD_cmd(paths=None, value=None, movedown=None, tag=None):
    """:tag_toggle <character>

    Toggle a tag <character>.
    """
    result = client.original['tag'](client.fm, paths, value, movedown, tag)
    client.ranger_tag_send()
    return result


# Overwrite the old one
if 'tag_toggle' in ranger.fm.commands.commands:
    LOG.debug("Share tag command")
    client.original['tag'] = ra.Actions.tag_toggle
    client.command['tag'] = client.ranger_tag_get
    ranger.fm.commands.commands['tag_toggle'] = rc._command_init(rc.command_function_factory(tag_SQUAD_cmd))
    ra.Actions.tag_toggle = tag_SQUAD


def set_bookmark_SQUAD(self, key, val=None):
    """Set the bookmark with the name <key> to the current directory"""
    result = client.original['set_bookmark'](self, key, val)
    client.ranger_bookmark_send()
    return result


def set_bookmark_SQUAD_cmd(key, val=None):
    """Set the bookmark with the name <key> to the current directory"""
    result = client.original['set_bookmark'](client.fm, key, val)
    client.ranger_bookmark_send()
    return result


def unset_bookmark_SQUAD(self, key):
    """Delete the bookmark with the name <key>"""
    result = client.original['unset_bookmark'](self, key)
    client.ranger_bookmark_send()
    return result


def unset_bookmark_SQUAD_cmd(key):
    """Delete the bookmark with the name <key>"""
    result = client.original['unset_bookmark'](client.fm, key)
    client.ranger_bookmark_send()
    return result

# Overwrite the old one
if ('set_bookmark' in ranger.fm.commands.commands and
    'unset_bookmark' in ranger.fm.commands.commands):
    LOG.debug("Share bookmark command")
    client.original['set_bookmark'] = ra.Actions.set_bookmark
    client.original['unset_bookmark'] = ra.Actions.unset_bookmark
    client.command['bookmark'] = client.ranger_bookmark_get
    ranger.fm.commands.commands['set_bookmark'] = rc._command_init(rc.command_function_factory(set_bookmark_SQUAD_cmd))
    ra.Actions.set_bookmark = set_bookmark_SQUAD
    ranger.fm.commands.commands['unset_bookmark'] = rc._command_init(rc.command_function_factory(unset_bookmark_SQUAD_cmd))
    ra.Actions.unset_bookmark = unset_bookmark_SQUAD

# Copyright 2017 Alexey Aksenov. All rights reserved.
# Licensed under the Apache License, version 2.0:
# http://www.apache.org/licenses/LICENSE-2.0

import zmq
import time

context = zmq.Context()
sub = context.socket(zmq.SUB)
sub.connect('ipc:///tmp/ranger-squad-commands.ipc')
sub.setsockopt_string(zmq.SUBSCRIBE, '')

while True:
    topic, messagedata = sub.recv_multipart()
    print(topic, messagedata)

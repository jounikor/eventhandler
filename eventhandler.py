#
# Mockup v0.3 (c) 2018 by Jouni Korhonen
#
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org/>
#

import argparse
import exceptions
import errno
import socket
import select
import sys


class eventhandler(object):
    RECV = 0
    SEND = 1
    EXEP = 2
    TIME = 3
    RECVBLOCK = 1024
    TIMEOUT = 10

    #
    #
    def __init__(self,debug=False):
        self.recvhandlers = {}
        self.sendhandlers = {}
        self.timehandlers = {}
        self.debug = debug

    #
    # remove a handler with <handle> from any possible
    # handler list. 
    # TODO: a cleanup callback would be nice..
    #
    def unregisterandcloseanyhandler(self,handle):
        if (handle in self.recvhandlers):
            self.recvhandlers.pop(handle)
        if (handle in self.sendhandlers):
            self.sendhandlers.pop(handle)
        if (handle in self.timehandlers):
            self.timehandlers.pop(handle)

    #
    #
    # Handler must have the calling convention:
    #  data = handlerfunction(obj,handle,data)
    #
    # Where
    #  obj is a reference to eventhandler object
    #  handle is a File or Socket object
    #  data is anything like a set or array etc
    #
    # Returns
    #  data is None if this handler has to be removed
    #  data is not None if this same handlerfunction is to be re-registered
    #       with the original <handle> and returned <data>
    #
    # TODO:
    #  The handler should actually be an object with
    #  init(), exec() and exit() methods.. Now the
    #  current implementation just deals with functions.
    #
    #
    def registerhandler(self,type,sock,func,data=None):
        if (type == self.RECV):
            handlers = self.recvhandlers
        elif (type == self.SEND):
            handlers = self.sendhandlers
        else:
            errstr = "unsupported handler type {} registration".format(type)
            raise RuntimeError(errstr)

        if (sock in handlers):
            if (self.debug):
                print "duplicate handler {} registration for type {} and socket {}".format(func,type,sock)

        if (self.debug):
            print "registering handler type {} for {} and socket {}".format(type,func,sock)
        
        handlers[sock] = (self,func,data)

    #
    #
    def prepareselect(self):
        timeout = self.TIMEOUT
        if (self.debug):
            print "**recvhandlers: ", self.recvhandlers.items()
            print "**sendhandlers: ", self.sendhandlers.items()
        return self.recvhandlers.keys(),self.sendhandlers.keys(),timeout

    #
    #
    def numhandlers(self):
        num  = self.recvhandlers.__len__()
        num += self.sendhandlers.__len__()
        num += self.timehandlers.__len__()
        return num

    #
    #
    def handle(self,type,sock):
        if (self.debug):
            print "handling type {} for socket {}".format(type,sock)
        if (type == self.RECV):
            d = self.recvhandlers
        elif (type == self.SEND):
            d = self.sendhandlers
        elif (type == self.TIME):
            # No implementation at the moment..
            if (self.debug):
                print "timeout handler(s) expired.. no implementation yet!"
            return
        else:
            # no implementation for exceptional (EXEP) handlers
            errstr = "Don't know how to handle type = {}".format(type)
            raise RuntimeError(errstr)

        obj,func,data = d.pop(sock,(None,None,None))

        if (func == None):
            # This is a bit of dirty solution here.. a previous handler might have
            # already closed and removed a socket/handler, which then is still
            # "to be served" in the select.select() returned arrays..
            
            if (self.debug):
                print "handler for socket {} already removed".format(sock)
            return 


        data = func(obj,sock,data)

        if (data is not None):
            if (self.debug):
                print "Re-registering handler {} for socket {}".format(func,sock)
            d[sock] = (self,func,data)
        else:
            if (self.debug):
                print "removing handler {} for socket {}".format(func,sock)

    #
    #
    def wfe(self):
        inputs,outputs,timeout = self.prepareselect()
        readable,writeable,exceptional = select.select(inputs,outputs,inputs,timeout)
        return readable,writeable,exceptional

    #
    # All in one solution..
    #
    def run(self):
        while (self.numhandlers() > 0):
            readable,writeable,exceptional = self.wfe()
            
            if (not (readable or writeable or exceptional)):
                # timeout
                self.handle(self.TIME,None)
            else:
                for s in readable:
                    self.handle(self.RECV,s)
                for s in writeable:
                    self.handle(self.SEND,s)
                for s in exceptional:
                    self.handle(self.EXEP,s)
        
#
# Test Program..
#
#
#
#
#
#
#

def recvhandler(obj,clnt,serv):
    try:
        data = clnt.recv(eventhandler.RECVBLOCK)
    except socket.error, err:
        if (err.errno == errno.EAGAIN):
            if (args.debug):
                print "recv returned EAGAIN.. re-registering"
            return buf
    
    if (not data):
        if (args.debug):
            print "connection closed for {}".format(clnt.getpeername())
        
        clnt.close()
        serv.close()
        obj.unregisterandcloseanyhandler(serv)
        return None
    
    if (args.debug):
        print "recv from {} total {} bytes".format(clnt.getpeername(),data.__len__())
        print data

    obj.registerhandler(eventhandler.SEND,serv,sendhandler,(data,0,clnt))
    return None

#
#
def sendhandler(obj,serv,buf):
    data,sent,clnt = buf
    
    try:
        n = serv.send(data[sent:])
    except socket.error, err:
        if (err.errno == errno.EAGAIN):
            if (args.debug):
                print "send returned EAGAIN.. re-registering"
            return buf
    
    if (args.debug):
        print "sent to {} total {} bytes".format(serv.getpeername(),n)

    if (n <= 0):
        if (args.debug):
            print "send socket connection broken"
        serv.close()
        clnt.close()
        obj.unregisterandcloseanyhandler(clnt)
        return None

    sent += n

    if (sent < data.__len__()):
        # re-registration.. thus update auxilary data
        return (data,sent,cnlt)
       
    # read more data from client
    obj.registerhandler(eventhandler.RECV,clnt,recvhandler,serv)
    return None

#
#
def accepthandler(obj,sock,addr):
    clnt,peer = sock.accept()
    if (args.debug):
        print "New connection from '{}' to {}:{}".format(peer,addr[0],addr[1])
    
    try:
        serv = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        serv.connect(addr)
        serv.setblocking(1)
        clnt.setblocking(1)
        #serv.settimeout(1)
        #clnt.settimeout(1)
    except:
        if (args.debug):
            print "connecting to {} failed".format(addr)
        clnt.close()
    else:
        obj.registerhandler(eventhandler.RECV,clnt,recvhandler,serv)
        obj.registerhandler(eventhandler.RECV,serv,recvhandler,clnt)
    
    return addr

#
#
#
def initproxy( port ):
    prxy_sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    prxy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    prxy_sock.setblocking(0)
    prxy_sock.bind( ("",port) )
    prxy_sock.listen(10)

    if (args.debug):
        print "listening in {}".format(prxy_sock.getsockname())
    return prxy_sock

def connectserver( name, port ):
    serv_sock = socket.socket(socket.AF_INT,socket.SOCK_STREAM)
    serv_sock.connect( (name,port) )
    serv_sock.setblocking(0)

    return serv_sock


#
#

SERVER = "www.deadcoderssociety.net"
PORT_NAKED = 80
PORT_SSL   = 443

servernamestr = "Server FQDN to connect to. Defaults to '{}'.".format(SERVER)
serverportstr = "Server port to connect to. Defaults to {}.".format(PORT_SSL)

prs = argparse.ArgumentParser()
prs.add_argument("listenport",metavar="listenport",type=int,help="Port number to listen to incoming connections.")
prs.add_argument("-s","--server",metavar="server",type=str,help=servernamestr, default=SERVER)
prs.add_argument("-p","--port",metavar="port",type=int,help=serverportstr, default=PORT_SSL)
prs.add_argument("-d","--debug",dest="debug",action="store_true",default=False,help="Show debug output.")
args = prs.parse_args()

#
#

if (__name__ == "__main__"):
    handler = eventhandler(args.debug)
    prxy = initproxy(args.listenport)
    
    handler.registerhandler(eventhandler.RECV, prxy, accepthandler, (args.server, args.port))
    handler.run()
    prxy.close()



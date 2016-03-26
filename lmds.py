## \file lmds.py
# Main API for LMDS.

from pathlib import Path
import multiprocessing as mp
from queue import Empty, Full
from enum import Enum
from signal import signal, alarm, SIGINT, SIGQUIT, SIGTERM, SIGALRM, SIG_DFL

## Global pool of worker processes
#
#  This is a global pool of worker processes intended for any
#  use. This variable is an instance of [multiprocessing.Pool].
#
#  [multiprocessing.Pool]: https://docs.python.org/3.5/library/multiprocessing.html#multiprocessing.pool.Pool
workers = mp.Pool()

## Run a function asynchronously
#
#  Arguments:
#  - `func` The function to run asynchronously.
#  - `args=None<[]>` The positional arguments to pass to the function.
#  - `kwargs=None<{}>` The keyword arguments to pass to the function.
#
#  Returns an instance of [multiprocessing.pool.AsyncResult] that can be used to
#  get the return value of when the function is done.
#
#  [multiprocessing.pool.AsyncResult]: https://docs.python.org/3.5/library/multiprocessing.html#multiprocessing.pool.AsyncResult
def runAsync(func, args=None, kwargs=None):
    if args   == None: args   = ()
    if kwargs == None: kwargs = {}
    return workers.apply_async(func, args, kwargs)

# Internal.
#
# An enum. Contains the flags for the event loop.
class Events(Enum):
    done = 1       # We have have been asked to shut down.
    newMessage = 2 # There is at least one message to process.
    tick = 3       # Server tick event.

# Handler for SIGINT, SIGQUIT, SIGTERM
def exitHandler(_, _):
    loop.set(events.done)

# Handler for SIGALRM tick
def tickHandler(_, _):
    loop.set(events.tick)
    alarm(0.002)

## Enhanced version of [multiprocessing.Event] with support for multiple types
#  of events.
#
#  This class is thread and process safe.
#  
#  Call `set(flag)` to set the specified flag, where `flag` can be any value.
#
#  Call `is_set([flag])` to check if the specified flag is set. If flag is not
#  specified, then `is_set` checks if any flag is set.
#
#  Call `clear([flag])` to clear the specified flag. If flag is not specified,
#  then `clear` clears all flags.
#
#  Call `wait([flag])` to block until the specified flag is set. If flag is not
#  specified then `wait` blocks until any flag is set. `wait` does NOT return
#  the flag that was set, neither does it support a timeout value.
class Event(mp.Event):
    ## Construct a new instance of `Event`.
    #  
    # This constructor accepts no arguments.
    def __init__(self):
        Event.__init__(self)
        self.flags = []

    ## Check if a flag is currently set.
    #
    #  Arguments:
    #  - `flag=None` The flag to check.
    #
    #  This function returns `True` if the specified flag is set, otherwise
    #  `False`. If flag is not specified, the function returns `True` if
    #  any flag is set, otherwise `False`.
    def is_set(self, flag=None):
        if flag == None:
            return Event.is_set()
        else:
            return flag in flags
    
    ## Set the specified flag.
    #
    #  Arguments:
    #  - `flag` The flag to set. Can be any value.
    def set(self, flag):
        mp.Event.set()
        if not flag in flags:
            flags.append(flag)

    ## Clear the specified flag.
    #
    # Arguments:
    # - `flag=None` The flag to clear.
    #
    # Clears the specified flag. If `flag` is unspecified, the function will
    # clear all flags.
    def clear(self, flag=None):
        if flag == None:
            mp.Event.clear()
            flags.clear()
        else:
            if flag in flags:
                flags.remove(flag)
            if len(flags) == 0:
                mp.Event.clear()
    
    ## Wait for specified flag to be set.
    #
    #  Arguments:
    #  - `flag=None` The flag to wait for.
    #
    #  This function blocks until the specified flag is set. If no flag is
    #  specified, it waits until any flag is set. Unlike
    #  [multiprocessing.Event], it provides no timeout argument. This function
    #  always returns `None`.
    #
    #  [multiprocessing.Event]: http://docs.python.org/3/library/multiprocessing.html#multiprocessing.Event
    def wait(self, flag=None):
        while(True):
            mp.Event.wait()
            if flag == None:
                return
            if flag in flags:
                return
        
## Lock wrapper.
# 
# Used to aid in migrating to read-write locks later. Duplicates the
# [multiprocessing.Lock] API.
#
# [multiprocessing.Lock]: http://docs.python.org/3/library/multiprocessing.html#multiprocessing.Lock
class Lock:
    ## Construct a new instance of `Lock`.
    #
    #  Construct a new instance of `Lock`. This constructor accepts no arguments.
    def __init__(self):
        self.lock = mp.Lock()

    ## Acquire the lock.
    #
    #  Arguments:
    #  - `blocking=True` 
    def acquire(self, blocking=True, timeout=-1):
        self.lock.acquire(blocking, timeout)

    def release(self):
        self.lock.release()

# Enhanced version of the list class with internal lock
# and some thread-safe asyncronous functions
class LMDSList(list, Lock): # TODO use RWLock
    def _appendSafe(self, item):
        self.acquire()
        self.append(item)
        self.release()

    def appendAsync(self, item):
        runAsync(self._appendSafe, self, item)

    def _insertSafe(self, index, item):
        self.acquire()
        self.insert(index, item)
        self.release()

    def insertAsync(self, index, item):
        runAsync(self._insertSafe, self, index, item)

    def _removeSafe(self, item):
        self.acquire()
        self.remove(item)
        self.release()

    def removeAsync(self, item):
        runAsync(self._removeSafe, self, item)

# Single-threaded version of Queue
class STQueue(list):
    def put(self, item):
        self.insert(0, item)

    def get(self):
        if len(self) < 0:
            return self.pop()
        else:
            raise Empty()

# Event handler list
class EventHandlerList:
    def __init__(self):
        self.handlers = dict()
        self.nextID = 0
        
    def add(self, function, args=None, kwargs=None):
        # increment nextID but use the unincremented value
        # for this id
        ID = self.nextID++

        handler = [function, args, kwargs]
        if handler.args == None: handler.args = ()
        if handler.kwargs == None: handler.kwargs = {}

        self.handlers[ID] = handler

        return ID

    def remove(self, ID):
        if ID in self.handlers:
            del self.handlers[ID]

    def update(self, ID, function=None, args=None, kwargs=None):
        handler = self.handlers[ID]

        if function != None:
            handler[0] = function

        if args != None:
            handler[1] = args

        if kwargs != None:
            handler[2] = kwargs

    def call(self):
        for handler in self.handlers.values():
            handler[0](*handler[1], **handler[2])

# Improved version of the dict class with internal lock
# and some thread-safe asyncronous functions
class LMDSDict(dict, Lock): # TODO use RWLock
    def _add(self, key, value):
        self.acquire()
        self[key] = value
        self.release()

    def addAsync(self, key, value):
        runAsync(self._add, self, key, value)

    def _remove(self, key):
        self.acquire()
        del self[key]
        self.release()

    def removeAsync(self, key):
        runAsync(self._remove, self, key)

loop = Event()
inputs = LMDSList()
modules = LMDSDict()
exitFunctions = []

class Module:
    class Events(Enum):
        ready = True
        unready = False
        
    def __init__(self):
       modules.append(self)
       self.handlerLists = dict()
       self._ready = False
       for event in Events:
           self.handlerLists[event] = EventHandlerList()

    #
    # Private Module API:
    #     Use only from within this module.
    #

    # Called every 20 ms by the main process.
    def tick():
        pass

    def setReady(self, ready):
        if self._ready != ready:
            self._ready = ready

            self.handlerLists[Events(ready)].call()

    def getReady(self):
        return self._ready

    #
    # Event Handler API:
    #

    # The handler passed to this function will be called with the specified
    # arguments when the specified event occures. This function returns an
    # id that can be used to remove the handler. The event is specified as
    # a member of Module.Events.
    def addHandler(self, event, function, args=None, kwargs=None):
        return self.handlerLists[event].add(function, args, kwargs)

    def removeHandler(self, event, ID):
        self.handlerLists[event].remove(ID)

    def updateHandler(self, event, ID, function=None, args=None, kwargs=None):
        self.handlerLists[event].update(ID, function, args, kwargs)
    

class Output:
    

# Subclass this class to create a processor. Create processMessage(message),
# which will be called to submit a message for processing. When finished,
# call self.sendMessage(message) to send the message on down the chain. If you
# are doing heavy processing, use RequeueingProcessor instead.
class Processor:
    def __init__(self, processors=None):
        self.processors = processors

    def addProcessor(self, processor):
        self.processors.append(processor)

    def sendMessage(self, message):
        # Do not copy message if we have only one target processor
        if len(processors) == 1:
            processors[0].processMessage(message)
        elif len(processors) == 0:
            pass; # drop the message of we have no target processors
        else:
            for processor in processors:
                processor.processMessage(message.copy())

# Use this class as you would Processor. This class is used to avoid spending
# to much time processing the messages from one input. It registers as an input,
# and queues its messages when done processing. It waits until called by the
# core to send its messages on. This class effectively outputs its messages
# to itself.
class RequeueingProcessor(Processor):
    def __init__(self, processors=[]):
        Processor.__init__(self, processors)
        self.queue = STQueue()
        inputs.append(self)

    def sendMessage(message):
        self.queue.put(message)

    def processMessages(self, maxLoops):
        for _ in range(0, maxLoops):
            try:
                message = self.queue.get()
            except Empty:
                break

            # we have to call the base class version of sendMessage
            Processor.sendMessage(self, message)

# Subclass this class to create a new type of input. Create run(), which
# will be called in a new process. Inside run, call self.processMessage(message)
# to run a message through the processing chains. Parameter processors of the
# constructor is the list of processors to which the message will be sent. A
# *shallow copy* of the message will be sent to every processor in the list.
# run is passed a keyword argument 'exitEvent' which is an event that will
# be set to tell the process to exit. The process has one second to exit
# before it will be terminated
class Input(Processor):
    class InputProcess:
        def __init__(self, queue, newMessage, target, args, kwargs):
            self.exitEvent = Event()
            kwargs["exitEvent"] = exitEvent
            Process.__init__(self, target, args, kwargs)
            # used to transfer messages to the main process
            self.queue = queue
            # used to indicate to the main process that a new message
            # is ready for processing
            self.newMessage = newMessage

        def processMessage(self, message):
            self.queue.put(message)
            self.newMessage.set()
            
    def __init__(self, processArgs=(), processKWArgs={}, processors=[]):
        Processor.__init__(processors)
        self.queue = Queue()
        self.process = InputProcess(self.run, queue, processArgs, processKWArgs)
        self.process.start()

    def _run(*args, **kwargs):
        signal(SIGINT, SIG_DFL)
        signal(SIGQUIT, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        # Call statically; we don't want to pass self to run.
        # The process probably won't need it.
        Input.run(*args, **kwargs)

    def exit():
        process.exitEvent.set()

    def processMessages(self, maxLoops):
        for _ in range(0, maxLoops):
            try:
                message = self.queue.get(False)
            except Empty:
                break;

            self.sendMessage(message)
            
# To create an output, create a class with the method processMessage(message).

class LMDSException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return message

class NonexistantRuleError(LMDSException):
    def __init__(self, rule, message):
        self.rule = rule
        LMDSException.__init__(self, message)

    def __str__(self):
        return repr(self.rule) + ": " + self.message

from pathlib import Path
from threading import Event, Thread, Lock
from queue import Queue, Empty
from signal import signal, SIGINT, SIGQUIT, SIGTERM

# Lock wrapper. Used to aid in migrating to read-write
# locks later.
class LMDSLock:
    def __init__(self):
        self.lock = Lock()

    def acquire(self, blocking=True, timeout=-1):
        self.lock.acquire(blocking, timeout)

    def release(self):
        self.lock.release()

# helper functions
def runAsync(func, *args):
    Thread(target=func, args=args).run()

# Enhanced version of the list class with internal lock
# and some thread-safe asyncronous functions
class LMDSList(list, LMDSLock): # TODO use RWLock
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

# Improved version of the dict class with internal lock
# and some thread-safe asyncronous functions
class LMDSDict(dict, LMDSLock): # TODO use RWLock
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

done = Event() # set to true when told to exit
rules = LMDSList()
sources = LMDSList()
targets = LMDSDict()
messages = Queue()
exitFunctions = []

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

class Message:
    pass

class Rule:
    def __init__(self, match, action):
        self.match = match
        self.action = action

    def __eq__(self, other):
        return self.match == other.match and self.action == other.action

# builtin rule actions
class Actions:
    # dispatch message to target specified by message.target
    def dispatchToTarget(message):
        targets.acquire()
        if message.target in targets:
            del message.target
            targets[message.target].dispatch(message)
            return True
        else:
            pass # TODO: handle properly once we have a logging system
            
    # drop the message
    def drop(message):
        return true

# builtin rule matchers
class Matchers:
    # matches any message containing a target attribute
    def target(message):
        return hasattr(message, 'target')
            
# some preconfigured rules
class Rules:
    # sends the message to the target specified in the
    # target attribute (if possible)
    dispatchToTarget = Rule(Matchers.target, Actions.dispatchToTarget)

# signal handler for 'exit' signals (INT, QUIT, TERM)
def exitHandler(number, frame):
    done.set()

# Any messages not dispatched are dropped.
def processMessage(message):
    
    for rule in rules:
        # If rule.match returns true then call rule.action.
        # If either returns false the message has not been
        # handled completely
        if rule.match(message) and rule.action(message):
            break;

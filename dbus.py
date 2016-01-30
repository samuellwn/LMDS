import glibmainloop
import lmds
import dbus

# Turns the strings 'system' or 'session' into the
# system bus or the session bus
def _getBus(bus):
    if bus == 'system':
        return dbus.SystemBus(mainloop=glibnainloop.loop)
    elif bus == 'session':
        return dbus.SessionBus(mainloop=glibmainloop.loop)
    else:
        return bus

class DBusTarget:
    def __init__(self, bus, name, obj):
        self.bus = _getBus(bus)
        self.name = name
        self.object = obj
        self.iface = dbus.Interface(self.bus.get_object(name, obj),
                                    dbus_interface='org.samuellwn.LMDS.Message')

    def _dbusDictPack(d):
        if type(d) == dbus.Dictionary:
            return d
        
        result = dbus.Dictionary(signature='a{sv}')
        for item in d.items():
            if isinstance(item[1], list):
                result[item[0]] = _dbusListPack(item[1])
            elif isinstance(item.value, dict):
                result[item[0]] = _dbusDictPack(item[1])
            else:
                result[item.key] = item.value
        return result

    def _dbusListPack(l):
        if type(l) == dbus.Array:
            return l
        
        result = dbus.Array(signature='av')
        for item in l:
            if isinstance(item, list):
                result.append(_dbusListPack(item))
            elif isinstance(item, dict):
                result.append(_dbusDictPack(item))
            else:
                result.append(item)
        return result

    def dispatch(self, message):
        self.iface.sendMessage(_dbusDictPack(message))

class DBusSource(dbus.service.Object):
    def __init__(self, bus, name, obj):
        self.bus = _getBus(bus)
        self.busName = BusName(name, self.bus)
        dbus.service.Object.__init__(self, self.busName, obj)
        self.name = name
        self.object = obj

    @dbus.service.method(dbus_interface='org.samuellwn.LMDS.Message',
                         in_signature='a{sv}')
    def sendMessage(self, msg):
        message = Message()
        message.__dict__ = msg
        runAsync(messages.put, messages, msg)

        

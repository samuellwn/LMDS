import glibmainloop
import lmds
import dbus

class DesktopNotifyTarget:
    def __init__(self):
        self.bus = dbus.SessionBus(mainloop=glibmainloop.loop)
        self.notify = dbus.Interface(self.bus.get_object('org.freedesktop.Notifications',
                                                         '/org/freedesktop/Notifications'),
                                     dbus_interface='org.freedesktop.Notifications')

    def dispatch(self, message):
        appName = ''
        #replaceId = 0
        icon = ''
        summary = message.name
        body = message.message
        
        if hasattr(message, 'appName'):
            appName = message.appName

        if hasattr(message, 'icon'):
            icon = message.icon

        #if hasattr(message, 'replaceId'):
        #    replaceId = message.replaceId
                  
        notify.Notify(appName, 0, icon, summary, body, [], dict(), -1)


        

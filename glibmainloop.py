import gobject
import lmds

loop = gobject.MainLoop()
lmds.runAsync(loop.run, loop)

def stopLoop():
    loop.quit()
    
# necessary for md to quit when this plugin is loaded
lmds.exitFunctions.append(stopLoop)

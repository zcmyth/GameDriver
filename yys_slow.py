from game import Game
from action import SimpleAction
from devices import Builder
from adb_device import AdbDevice
import time
import utils

def finish(g):
    if g.click('finish'):
        time.sleep(1)
        g.click((100,100))
    	return True
    return False


def main():
    device = (Builder().with_device(AdbDevice)
            .with_limit(0.1)  # one action per second
            .with_blur(5)   # random change click point
            .build())
    game = Game(device, idle_time=30)
    game.addAction(SimpleAction('busy'))
    game.addAction(SimpleAction('cancel'))
    game.addAction(SimpleAction('next'))
    game.addAction(SimpleAction('challenge'))
    game.addAction(SimpleAction('prepare'))
    game.addAction(SimpleAction('fight'))
    game.addAction(finish)
    game.start()


if __name__ == "__main__":
    main()

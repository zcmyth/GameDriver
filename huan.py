from game import Game
from utils import COMMON
from action import SimpleAction, multiClick
import time
from devices import Builder
from adb_device import AdbDevice

BLACKLIST = [
    'jinlanhua',
    'rose',
    'shoujue',
    'neidan'
]


def choose(g):
    point = g.find('choose')
    if point:
        return g.click((point[0], point[1] + 80))
    return False


def guaji(g):
    if multiClick(g, ['guaji', 'hell4']):
        print '\a'
        print 'chuang shuo 20 mins'
        start = time.time()
        while time.time() - start < 20 * 60:
            print 'check chuang shuo'
            g.screenshot()
            if choose(g):
                return True
            time.sleep(60)
        print '\a'
        print 'cannot chuang shuo'
        exit()
    return False


def guaji_if_no_money(g):
    if g.find('nomoney'):
        multiClick(g, ['nmclose', 'close'])
        return guaji(g)
    return False


def buy(g):
    point = g.find('buy')
    if point:
        time.sleep(1)
        g.screenshot()
        need = g.find('need')
        if not need:
            return multiClick(g, [point, 'close'])
        for item in BLACKLIST:
            if g.find(item):
                g.click('close')
                return guaji(g)
        return multiClick(g, ['need', 'buy', 'close'])
    return False


def main():
    device = (Builder().with_device(AdbDevice)
              .with_limit(1)  # one action per second
              .with_blur(5)   # random change click point
              .build())
    game = Game(device)
    game.addAction(choose)
    game.addAction(guaji_if_no_money)
    game.addAction(buy)
    for image in COMMON:
        game.addAction(SimpleAction(image))
    game.idle = lambda g: g.click('huan')
    game.start()

if __name__ == "__main__":
    main()

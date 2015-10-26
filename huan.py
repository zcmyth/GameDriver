from game import Game
from utils import rate_limited, COMMON
from action import SingleClickAction, MultiClickAction
import time

BLACKLIST = [
    'jinlanhua',
    'rose',
    'shoujue',
    'neidan'
]

@rate_limited(0.01, block=False)
def clickTask(g):
    if click(g, 'huan'):
        print 'dumb ass move'

def task(g):
    point = g.find('choose')
    if point:
        g.click((point[0], point[1] + 80))

def click(g, image):
    g.screenshot()
    return g.clickImage(image)

def guaji(g):
    click(g, 'guaji')
    click(g, 'hell4')
    print '\a'
    print 'chuang shuo 20 mins'
    time.sleep(20 * 60)

def guaji_if_no_money(g):
    if g.find('nomoney'):
        click(g, 'nmclose')
        click(g, 'close')
        guaji(g)

def buy(g):
    point = g.find('buy')
    if point:
        g.screenshot()
        need = g.find('need')
        if not need:
            g.click(point)
            click(g, 'close')
            click(g, 'huan')
            click(g, 'huan')
            return
        for item in BLACKLIST:
            if g.find(item):
                click(g, 'close')
                guaji(g)
                return
        click(g, 'need')
        click(g, 'buy')
        click(g, 'close')
        click(g, 'huan')
        click(g, 'huan')

def main():
    game = Game()
    game.addAction(clickTask)
    game.addAction(task)
    game.addAction(guaji_if_no_money)
    game.addAction(buy)
    for image in COMMON:
        game.addAction(SingleClickAction(image))
    game.start()

if __name__ == "__main__":
    main()
    #game = Game()
    #game.screenshot()
    #print game.find('task')

import common
import time

sys.path.append("..")
from game import Game
from action import SimpleAction
from devices import create


def baigui(g):
    if g.click("baigui_start"):
        time.sleep(3)
        g.click((0.5, 0.7))
        time.sleep(2)
        g.click((0.9, 0.9))
        time.sleep(3)
        i = 0
        while not g.click("baigui_end"):
            g.click((0.73, 0.48))
            time.sleep(0.7)
            if i > 40 and i % 10 == 0:
                g.screenshot()
            i = i + 1
        time.sleep(2)
        g.click((0.56, 0.23))
    return False


def main():
    game = Game(create(rate_limit=2, blur=0.005), debug=True)
    common.handle_common_interruption(game)
    game.addAction(baigui)
    game.start()


if __name__ == "__main__":
    main()

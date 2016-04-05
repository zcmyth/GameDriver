from game import Game
from adb_device import AdbDevice


if __name__ == "__main__":
    game = Game(AdbDevice())
    game.screenshot()
    print game.click('neidan')
    

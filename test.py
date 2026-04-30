from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

tiles = TilesConverter.string_to_34_array(man='123', pin='345', sou='678', honors='1221')

shanten = Shanten()
print(shanten.calculate_shanten(tiles))
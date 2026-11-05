"""재화가 부족합니다: the game's own word that a growth press had nothing behind it. Nothing was spent.

Seen 11-05 at 1366x768 on skill, blessing and gear enhance and gear awaken, at (682,84), within half a second of the
press and for nearly 3 seconds. Item names start below this band, so it holds nothing else with these words.
"""
import owner_text as text

BAND=(400,60,560,50)
RESULT='short_of_coins'


def shown(frame,root=None):
    """False on a frame with no real pixels, or when the words cannot be read: the older result checks then answer."""
    if getattr(frame,'hi',None) is None:return False
    try:rows=text.read(root,frame,BAND,scale=2,minimum=.6)
    except (OSError,ValueError,RuntimeError):return False
    return any('부족' in text.clean(row['text']) for row in rows)

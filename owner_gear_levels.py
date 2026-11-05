"""Which worn item to enhance next: the lowest of its grade.

Stones are per grade, and spending them all on one item left the rest at +0 (hat +31, shoes +0).
Tile readings only choose the order. The two-frame reading before each input still decides it.
"""
import re

STEP = 3
GRID_RULE = 'right'  # the item grid keeps to the right edge at any width
# A two-digit +31 needs the wide crop and a lone +5 only reads on the narrow one (897x479 frames).
CROPS = ((12, 22, 24, 13), (18, 24, 16, 10))
INK = 175


def _real_cell(row):
    from owner_hd import real_box
    s = row['slot']
    return real_box((s['cell_x'], s['cell_y'], s['cell_w'], s['cell_h']), rule=GRID_RULE)


def real_tile_level(root, real, row):
    """The +N in a tile's lower right, read on the real screen. No white ink there means +0, ink that cannot be read
    means not known."""
    import numpy as np
    from owner_text import read_area
    x, y, w, h = _real_cell(row)
    part = real[y + h // 2:y + h, x + 8:x + w + 2]
    if int((part.min(axis=2) > INK).sum()) < 30:
        return 0
    # Plain reads 3 and 1 best and white digits over a pale icon worst. Lifted out on white, the other way round.
    # A pale icon can also reach into the crop and join the digits, so the last tries hold to the corner they sit in,
    # real pixels at the tile's lower right: +14 on white trousers was unknown on every run with the wider crop (18:47).
    corner = real[y + h - 17:y + h - 2, x + w - 32:x + w]
    for area, scale, floor in ((part, 2, .75), (_lifted(part), 3, .9), (corner, 2, .75), (_lifted(corner), 3, .9)):
        for found in read_area(root, area, language='number', scale=scale, minimum=floor):
            match = re.search(r'\+\s*(\d{1,2})$', found['text'].strip())
            if match:
                return int(match[1])
    return None


def _lifted(part):
    import numpy as np
    return np.stack([255 - (part.min(axis=2) > INK).astype(np.uint8) * 255] * 3, axis=2)


def tile_level(root, frame, row):
    """The +N on a tile. A tile with no digit pixels is +0 and needs no reader."""
    import cv2
    import numpy as np
    from tools.ocr_support import get_paddle_engine
    if getattr(frame, 'hi', None) is not None:
        return real_tile_level(root, np.asarray(frame.hi), row)
    x, y = row['slot']['cell_x'], row['slot']['cell_y']
    if int((frame[y + 24:y + 35, x + 18:x + 36].min(axis=2) > 190).sum()) < 3:
        return 0
    engine = get_paddle_engine(root, language='number')
    for dx, dy, w, h in CROPS:
        crop = cv2.resize(frame[y + dy:y + dy + h, x + dx:x + dx + w], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        crop = cv2.copyMakeBorder(crop, 12, 12, 12, 12, cv2.BORDER_REPLICATE)
        for page in engine.predict(crop):
            for text in page.get('rec_texts', ()):
                found = re.fullmatch(r'\+(\d{1,2})', str(text).strip())
                if found:
                    return int(found[1])
    return 0


def levels_of(root, frame, rows, seen=None, selected=None):
    """Index to level, None when not known. A value this visit proved beats a tile reading that came up short.

    The selected tile shows a tick instead of its +N. It read as +0, so whatever the screen opened on was picked as the
    lowest and took the stones: +13 legs went first with a rare ring at +0 (18:20).
    """
    seen = seen or {}
    levels = {}
    for row in rows:
        index = row['index']
        read = None if index == selected else tile_level(root, frame, row)
        known = [value for value in (read, seen.get(index)) if value is not None]
        levels[index] = max(known) if known else None
    return levels


def lowest_first(rows, levels, priority=None):
    """Not known goes last. Picking another item uncovers a selected tile for the next turn."""
    priority = priority or {}

    def key(row):
        level = levels.get(row['index'], 0)
        return (level is None, level or 0, priority.get(row['index'], 3), row['index'])
    return sorted(rows, key=key)


def ceiling_for(chosen, rows, levels):
    """Stop level for this turn. None means no other known item of this grade is waiting."""
    others = [levels.get(row['index'], 0) for row in rows
              if row['index'] != chosen['index'] and row.get('grade') == chosen.get('grade')]
    others = [level for level in others if level is not None]
    return min(others) + STEP if others else None


def real_worn(real, row):
    """Worn, not worn or unknown, by the orange E badge in the tile's corner on the real screen."""
    import numpy as np
    x, y, w, h = _real_cell(row)
    part = np.asarray(real)[max(0, y - 2):y + h // 2, x + w // 2:x + w + 4].astype(np.int16)
    if not part.size:
        return None
    orange = int(((part[:, :, 0] - part[:, :, 2] > 90) & (part[:, :, 0] > 150) & (part[:, :, 1] > 70)).sum())
    if orange >= 30:
        return True
    return False if orange <= 2 else None


def install_real_rows(native):
    """The grid reader tells worn from unworn by small pictures that do not survive the larger window.
    Its grades and places still hold, so only that one answer comes from the real pixels."""
    from functools import wraps
    ordinary = native.inspect_growth_equipment
    if getattr(ordinary, '_owner_real_rows', False):
        return

    @wraps(ordinary)
    def inspect(detector, frame, *args, **kwargs):
        rows = ordinary(detector, frame, *args, **kwargs)
        real = getattr(frame, 'hi', None)
        if real is None:
            return rows
        selected = native._growth_selected_slot(frame, rows)
        for row in rows:
            if row.get('index') == selected or row.get('grade') not in ('흰', '파랑', '보라'):
                continue
            worn = real_worn(real, row)
            if worn is not None:
                row.update(equipped=worn, equipped_state='장착' if worn else '미장착')
        return rows
    inspect._owner_real_rows = True
    native.inspect_growth_equipment = inspect

"""Which worn item to enhance next: the lowest of its grade.

Stones are per grade, and spending them all on one item left the rest at +0 (hat +31, shoes +0).
Tile readings only choose the order. The two-frame reading before each input still decides it.
"""
import re

STEP = 3
# A two-digit +31 needs the wide crop and a lone +5 only reads on the narrow one.
CROPS = ((12, 22, 24, 13), (18, 24, 16, 10))


def tile_level(root, frame, row):
    """The +N on a tile. A tile with no digit pixels is +0 and needs no reader."""
    import cv2
    from tools.ocr_support import get_paddle_engine
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


def levels_of(root, frame, rows, seen=None):
    """Index to level. A value this visit proved beats a tile reading that came up short."""
    seen = seen or {}
    return {row['index']: max(tile_level(root, frame, row), seen.get(row['index'], 0)) for row in rows}


def lowest_first(rows, levels, priority=None):
    priority = priority or {}
    return sorted(rows, key=lambda row: (levels.get(row['index'], 0), priority.get(row['index'], 3), row['index']))


def ceiling_for(chosen, rows, levels):
    """Stop level for this turn. None means no other item of this grade is waiting."""
    others = [levels.get(row['index'], 0) for row in rows
              if row['index'] != chosen['index'] and row.get('grade') == chosen.get('grade')]
    return min(others) + STEP if others else None

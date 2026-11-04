"""Read-only presentation for DKB schedule snapshots, independent of the bot.

The source row remains available on the PC; the image includes full status,
both timestamps and next-action text. No network, game input, or storage.
"""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

GROUPS = ('일일', '주간', '시간제', '상시·성장')
FONT = Path('C:/Windows/Fonts/malgun.ttf')
BOLD = Path('C:/Windows/Fonts/malgunbd.ttf')


def project(snapshot, group='전체'):
    """Return copies with original text; never infer completion from a status."""
    return [dict(row) for row in snapshot['rows'] if group == '전체' or row['group'] == group]


def pc_values(row):
    return (row['group'], row['name'], row['status'], row['last_at'],
            row['completed_at'], row['next'])


def configure_pc_table(tree):
    """Configure an existing six-column Treeview without replacing controls."""
    columns = ('group', 'name', 'status', 'recent', 'completed', 'next')
    tree.configure(columns=columns, show='headings')
    for key, title, width in zip(columns,
            ('구분', '콘텐츠', '상태', '최근 진행', '완료 확인', '다음 예정'),
            (70, 190, 215, 110, 110, 300)):
        tree.heading(key, text=title)
        tree.column(key, width=width, minwidth=60, stretch=key in ('name', 'status', 'next'))
    tree.tag_configure('verified', foreground='#116742')
    tree.tag_configure('failed', foreground='#a52d32')
    tree.tag_configure('pending', foreground='#40556c')


def fill_pc_table(tree, snapshot, group='전체'):
    """Use full source strings; preserve the selected item for the detail panel."""
    selected = tree.selection()
    tree.delete(*tree.get_children())
    for row in project(snapshot, group):
        tag = 'verified' if row.get('verified') else 'failed' if '실패' in row['status'] else 'pending'
        tree.insert('', 'end', iid=row['id'], values=pc_values(row), tags=(tag,))
    if selected and tree.exists(selected[0]):
        tree.selection_set(selected[0])


def wrap(draw, text, font, width):
    result = []
    for paragraph in str(text if text is not None else '—').split('\n'):
        if not paragraph:
            result.append(''); continue
        line = ''
        for char in paragraph:
            trial = line + char
            if line and draw.textlength(trial, font=font) > width:
                result.append(line); line = char
            else:
                line = trial
        result.append(line)
    return result or ['—']


def sheets(snapshot, group='전체'):
    """Return independent JPEG pages and captions with the original contract."""
    normal = ImageFont.truetype(str(FONT), 22)
    small = ImageFont.truetype(str(FONT), 19)
    namefont = ImageFont.truetype(str(BOLD), 23)
    titlefont = ImageFont.truetype(str(BOLD), 30)
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    width, inner = 720, 650
    pages = []
    for section in GROUPS:
        if group not in ('전체', section): continue
        rows = project(snapshot, section)
        for start in range(0, len(rows), 8):
            batch = rows[start:start + 8]
            cards = []
            for row in batch:
                name = wrap(draw, row['name'], namefont, 175)
                status = wrap(draw, row['status'], normal, 195)
                next_run = wrap(draw, row['next'], normal, 225)
                # The labels explicitly distinguish observations from confirmation.
                stamps = []
                if row['last_at'] not in ('—', '', None):
                    stamps += wrap(draw, '최근 ' + str(row['last_at']), small, 195)
                if row['completed_at'] not in ('—', '', None):
                    stamps += wrap(draw, '완료 확인 ' + str(row['completed_at']), small, 195)
                card_h = 20 + max(len(name) * 31, len(status) * 29 + len(stamps) * 25,
                                  len(next_run) * 29)
                cards.append((row, name, status, stamps, next_run, max(card_h, 68)))
            issue = snapshot.get('issue'); dropped = snapshot.get('dropped')
            foot = '처리 종료는 완료 확인이 아닙니다. 확인 시각은 실제 완료 시각과 다를 수 있습니다.'
            if issue: foot += '\n기록 수집 문제: ' + str(issue)
            if dropped: foot += '\n수집 누락: ' + str(dropped) + '건'
            footer = wrap(draw, foot, small, inner)
            height = 176 + sum(c[-1] for c in cards) + len(footer) * 26 + 30
            im = Image.new('RGB', (width, height), '#f1f4f8'); d = ImageDraw.Draw(im)
            d.text((30, 22), 'DKB · ' + section + ' 일정', font=titlefont, fill='#18304b')
            run = {'running':'실행 중', 'paused':'일시정지', 'stopped':'중지', 'error':'오류'}.get(snapshot['status'], snapshot['status'])
            d.text((30, 72), str(snapshot['day']) + '  ·  ' + str(run), font=normal, fill='#40556c')
            d.text((30, 108), '기준 ' + str(snapshot['generated_at'])[11:19], font=small, fill='#697b8c')
            d.rectangle((20, 135, 700, 174), fill='#e3eaf2')
            for x, title in ((30, '항목'), (218, '상태'), (428, '다음')):
                d.text((x, 142), title, font=small, fill='#334d67')
            y = 175
            for i, (row, name, status, stamps, next_run, h) in enumerate(cards):
                d.rectangle((20, y, 700, y+h), fill='white' if i % 2 == 0 else '#f8fafc')
                for j, line in enumerate(name): d.text((30, y+8+j*31), line, font=namefont, fill='#18304b')
                for j, line in enumerate(status): d.text((218, y+8+j*29), line, font=normal, fill='#344a60')
                for j, line in enumerate(stamps): d.text((218, y+8+len(status)*29+j*25), line, font=small, fill='#697b8c')
                for j, line in enumerate(next_run): d.text((428, y+8+j*29), line, font=normal, fill='#344a60')
                y += h
                d.line((20,y,700,y),fill='#dde5ef')
            y += 10
            for line in footer:
                d.text((30, y), line, font=small, fill='#6b5d54'); y += 26
            data = BytesIO(); im.save(data, 'JPEG', quality=92, subsampling=0)
            pages.append((data.getvalue(), f'DKB · {section} 일정  {start//8+1}/{(len(rows)+7)//8}'))
    return pages

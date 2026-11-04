exec((__import__('pathlib').Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest
import owner_schedule as schedule

class ScheduleLabels(unittest.TestCase):
 def test_every_catalogue_item_has_the_expected_stable_key(self):
  self.assertEqual(set(schedule.SHORT_NAMES),{i.key for i in schedule.ITEMS})
  for key,label in {'guide':'길라잡이','daily_quest':'일일 임무','achievement':'업적',
                    'album':'화첩','inventory':'인벤토리','daily24_dungeon':'24h 비경'}.items():
   self.assertEqual(schedule.SHORT_NAMES[key],label)

if __name__=='__main__':unittest.main()

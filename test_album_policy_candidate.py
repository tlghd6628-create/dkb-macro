import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from owner_album_policy_candidate import decision

class AlbumPolicy(unittest.TestCase):
 def row(self,**fields):
  value={'verified':True,'character':'test','entry':'test-album','action':'조각 등록','currency':'없음','amount':0,'completion_visible':False}
  value.update(fields);return value
 def test_register_and_completion_are_distinct(self):
  row=self.row();self.assertEqual(decision('조각 등록만',row,row),'allow')
  row=self.row(action='완성',currency='요혼석',amount=300)
  self.assertEqual(decision('조각 등록만',row,row),'skip')
  self.assertEqual(decision('완성',row,row),'allow')
 def test_never_guess_unknown_cost_or_absence(self):
  for row in (self.row(currency=None),self.row(amount=None),self.row(verified=False),self.row(currency='없음',amount=5)):
   self.assertEqual(decision('조각 등록만',row,row),'hold')
 def test_different_fresh_views_never_authorize(self):
  a=self.row();b=self.row(entry='other')
  self.assertEqual(decision('조각 등록만',a,b),'hold')
  b=self.row(action='완성',currency='요혼석',amount=300)
  self.assertEqual(decision('조각 등록만',a,b),'hold')
 def test_paid_soulstone_in_registration_also_skips(self):
  row=self.row(currency='요혼석',amount=20)
  self.assertEqual(decision('조각 등록만',row,row),'skip')
 def test_completion_button_stops_register_only(self):
  row=self.row(completion_visible=True)
  self.assertEqual(decision('조각 등록만',row,row),'skip')
  self.assertEqual(decision('조각 등록만',row,self.row()),'hold')
  row=self.row(completion_visible=True,currency=None,amount=None)
  self.assertEqual(decision('조각 등록만',row,row),'skip')
if __name__=='__main__':unittest.main()

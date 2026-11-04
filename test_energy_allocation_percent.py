"""Pure allocation and cloned settings tests; never opens a game/menu."""
import tempfile,unittest
from pathlib import Path
import bootstrap
from owner_energy_allocation_candidate import NAMES,allocation,weights,percent_units,equal_display,fingerprint
from owner_starter_choice_candidate import Choices

class Tests(unittest.TestCase):
 def data(self):return {'confirmed':{n:0 for n in NAMES},'manual_observations':[]}
 def equal(self):return {'version':1,'energy_mode':'balanced','energies':list(NAMES[:3])}
 def percent(self,a,b,c,d='0'):return {'version':1,'energy_mode':'percent','energies':[n for n,v in zip(NAMES,[a,b,c,d]) if float(v)>0],'energy_percentages':dict(zip(NAMES,[a,b,c,d]))}
 def test_default_display_sums100_but_internal_weights_are_exact_equal(self):
  display=equal_display(list(NAMES[:3]));self.assertEqual(list(display.values()),['33.33','33.33','33.34','0.00'])
  self.assertEqual(sum(percent_units(display).values()),10000);self.assertEqual(list(weights(self.equal()).values()),[1,1,1,0])
 def test46_stack_ignores_historic_ratio_debt(self):
  data=self.data();data['confirmed'].update({'생명':1,'여명':1,'몽환':1});data['manual_observations']=[{'balancing_only':True,'name':'생명','quantity':1}]
  result,cursor=allocation(46,self.equal(),data)
  self.assertEqual(result,{'생명':16,'여명':15,'몽환':15,'홍염':0});self.assertEqual(sum(result.values()),46)
 def test_requested_percentages_and_zero_exclusion(self):
  result,_=allocation(100,self.percent('50','30','20'),self.data());self.assertEqual(list(result.values()),[50,30,20,0])
  result,_=allocation(46,self.percent('0','100','0'),self.data());self.assertEqual(list(result.values()),[0,46,0,0])
 def test_persisted_cursor_prevents_repeated_single_box_tie_bias(self):
  data=self.data();seen=[]
  for _ in range(9):
   result,rounding=allocation(1,self.equal(),data);data['energy_ratio_rounding']=rounding
   name=next(n for n in NAMES if result[n]);data['confirmed'][name]+=1;seen.append(name)
  self.assertEqual(list(data['confirmed'].values()),[3,3,3,0]);self.assertEqual(seen[:3],list(NAMES[:3]))
 def test_changed_ratio_resets_rounding_without_historic_debt(self):
  data=self.data();_,rounding=allocation(1,self.equal(),data);data['energy_ratio_rounding']=rounding
  data['confirmed']['생명']=9999
  result,_=allocation(46,self.percent('50','50','0'),data)
  self.assertEqual(list(result.values()),[23,23,0,0])
 def test_sum_decimal_limits_and_nonfinite_values_rejected(self):
  for values in [('33.33','33.33','33.33','0'),('100.001','0','0','0'),('-1','101','0','0'),('NaN','0','0','0'),('Infinity','0','0','0')]:
   with self.assertRaises(ValueError):percent_units(dict(zip(NAMES,values)))
  self.assertEqual(sum(percent_units(dict.fromkeys(NAMES,'0')).values()),0)
 def test_existing_checkbox_file_loads_without_rewriting_or_losing_selected_set(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   store=Choices(root,'profile');data,revision=store.snapshot();self.assertEqual(revision,'missing')
   store.write(self.equal(),revision);before=store.path.read_bytes();loaded,newrevision=store.snapshot()
   self.assertEqual(loaded,self.equal());self.assertEqual(store.path.read_bytes(),before)
   updated=self.percent('50','30','20');store.write(updated,newrevision)
   self.assertEqual(store.snapshot()[0],updated)
 def test_invalid_sum_never_replaces_saved_settings(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'test_scratch') as root:
   store=Choices(root,'profile');store.write(self.equal(),'missing');before=store.path.read_bytes();data,revision=store.snapshot()
   data=self.percent('40','40','10')
   with self.assertRaises(ValueError):store.write(data,revision)
   self.assertEqual(store.path.read_bytes(),before)
 def test_ratio_fingerprint_treats_uniform_percent_and_equal_mode_consistently(self):
  two={'version':1,'energy_mode':'balanced','energies':list(NAMES[:2])}
  self.assertEqual(fingerprint(two),fingerprint(self.percent('50','50','0')))

if __name__=='__main__':unittest.main()

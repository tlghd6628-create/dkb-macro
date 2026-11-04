from pathlib import Path
exec((Path(__file__).parent/'bootstrap.py').read_text(encoding='utf-8'))
import unittest,tempfile,json
import numpy as np
from PIL import Image
from owner_controls import write_preview

class Cases(unittest.TestCase):
 def test_saved_png_is_exact_original_pixels(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   pixels=np.random.default_rng(4).integers(0,256,(48,89,3),dtype=np.uint8)
   image=Image.fromarray(pixels);meta={'width':89,'height':48,'time':'2026-11-02T00:00:00','game_input':False}
   path=write_preview(root,image,meta)
   self.assertTrue(np.array_equal(np.asarray(Image.open(path)),pixels))
   self.assertEqual(json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))['time'],meta['time'])
 def test_stale_or_resized_preview_is_not_saved(self):
  with tempfile.TemporaryDirectory(dir=T) as root:
   with self.assertRaises(ValueError):write_preview(root,Image.new('RGB',(3,3)),{'width':4,'height':4})
   self.assertFalse((Path(root)/'logs/manual-captures').exists())

if __name__=='__main__':unittest.main()

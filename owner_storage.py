"""Keep user-created diagnostic exports beside this portable launcher."""
from pathlib import Path
from functools import wraps

def install(gui):
 if getattr(gui,'_owner_diagnostic_storage',False):return
 import diagnostic_bundle
 original=diagnostic_bundle.create_bundle
 @wraps(original)
 def bundle(target):
  path=Path(original(target))
  if target is not gui:return path
  app=Path(gui.project.root).resolve()
  if path.resolve().parent!=(app/'logs/diagnostics').resolve() or path.suffix.lower()!='.zip':
   raise OSError('진단자료 원본 저장 위치 확인 필요')
  folder=app.parent.parent/'진단자료';folder.mkdir(parents=True,exist_ok=True)
  destination=folder/path.name
  if destination.exists():raise FileExistsError(destination)
  path.rename(destination)
  return destination
 diagnostic_bundle.create_bundle=bundle
 gui._owner_diagnostic_storage=True
 from owner_manual_diagnostics import install_button
 install_button(gui)

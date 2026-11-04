"""Normalize the observed native (profile, dependencies) helper contract."""
from collections.abc import Mapping
def runner_kwargs(value):
    if isinstance(value,tuple) and len(value)==2 and isinstance(value[1],Mapping):return dict(value[1])
    if isinstance(value,Mapping):return dict(value)
    raise TypeError('퀘스트 처리기 의존성 형식 확인 필요')

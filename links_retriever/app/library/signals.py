import random
import time
import typing

def score(signal: str, text: str) -> (str, float):
  #time.sleep(0.2)
  return signal, random.randint(0, 100) / 100

def get_signals() -> typing.List[str]:
  return [f"signal-{i}" for i in range(30)] 
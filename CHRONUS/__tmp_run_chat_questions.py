from pathlib import Path
import importlib.util

module_path = Path('06-Testing/chat_elon.py')
spec = importlib.util.spec_from_file_location('chat_elon', module_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

questions = [
    'What do you think about Mars?',
    'Are you worried about AI?',
    'Why do you work so hard?',
    'What happened with the Twitter acquisition?',
    'Are we living in a simulation?',
]

for i, q in enumerate(questions, start=1):
    print('\n' + '#' * 80)
    print(f'QUESTION {i}: {q}')
    print('#' * 80)
    mod.chat(q)

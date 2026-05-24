import re

def parse_diff(diff_content):
    chunks = []
    current_chunk = None
    lines = diff_content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('@@'):
            if current_chunk:
                chunks.append(current_chunk)
            match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)', line)
            current_chunk = {
                'header': line,
                'metadata': match.groups() if match else None,
                'added': [],
                'removed': [],
                'context_before': [],
                'context_after': [],
                'original': [],
                'replacement': []
            }
            # parse the chunk content
            i += 1
            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('diff '):
                chunk_line = lines[i]
                if chunk_line.startswith('+'):
                    current_chunk['added'].append(chunk_line[1:])
                    current_chunk['replacement'].append(chunk_line[1:])
                elif chunk_line.startswith('-'):
                    current_chunk['removed'].append(chunk_line[1:])
                    current_chunk['original'].append(chunk_line[1:])
                else:
                    if len(chunk_line) > 0:
                        c_line = chunk_line[1:] if chunk_line[0] in (' ', '\\') else chunk_line
                    else:
                        c_line = ''
                    if not current_chunk['added']:
                        current_chunk['context_before'].append(c_line)
                    else:
                        current_chunk['context_after'].append(c_line)
                    current_chunk['original'].append(c_line)
                    current_chunk['replacement'].append(c_line)
                i += 1
            continue
        i += 1
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

with open(r'c:\Users\THAAER\Desktop\project\scratch\diff_quick.txt', 'r', encoding='utf-8') as f:
    diff_content = f.read()

chunks = parse_diff(diff_content)
print(f"Total chunks parsed: {len(chunks)}")

with open(r'c:\Users\THAAER\Desktop\project\bro\quick\views.py', 'r', encoding='utf-8') as f:
    bro_content = f.read()

for index, chunk in enumerate(chunks):
    orig = '\n'.join(chunk['original'])
    repl = '\n'.join(chunk['replacement'])
    # Skip the import chunk (index 0)
    if index == 0:
        continue
    
    # Try to find replacement first (to see if it's already applied)
    if repl in bro_content:
        print(f"Chunk {index} is ALREADY APPLIED")
    elif orig in bro_content:
        print(f"Chunk {index} is NOT applied, but ORIGINAL is found (Can apply!)")
    else:
        print(f"Chunk {index} is NOT applied and ORIGINAL was NOT found in full. Let's inspect context.")
        print("Original context before:")
        print(chunk['context_before'])
        print("Original to replace:")
        print(chunk['removed'])

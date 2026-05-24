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

with open(r'c:\Users\THAAER\Desktop\project\bro\quick\views.py', 'r', encoding='utf-8') as f:
    bro_content = f.read()

applied_count = 0
already_applied = 0
failed_count = 0

for index, chunk in enumerate(chunks):
    if index == 0:
        # Skip import chunk as it's already there
        continue
    orig = '\n'.join(chunk['original'])
    repl = '\n'.join(chunk['replacement'])
    
    if repl in bro_content:
        already_applied += 1
    elif orig in bro_content:
        # Perform replacement
        bro_content = bro_content.replace(orig, repl)
        applied_count += 1
        print(f"Applied Chunk {index}")
    else:
        print(f"ERROR: Chunk {index} could not be matched!")
        failed_count += 1

if failed_count == 0:
    with open(r'c:\Users\THAAER\Desktop\project\bro\quick\views.py', 'w', encoding='utf-8') as f:
        f.write(bro_content)
    print(f"SUCCESS: Applied {applied_count} chunks, {already_applied} were already applied.")
else:
    print(f"FAILED: {failed_count} chunks could not be applied. Aborting file write.")

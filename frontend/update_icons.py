import os
import re

def get_relative_path(from_file, to_file):
    from_dir = os.path.dirname(from_file)
    rel_path = os.path.relpath(to_file, from_dir)
    if not rel_path.startswith('.'):
        rel_path = './' + rel_path
    if rel_path.endswith('.jsx'):
        rel_path = rel_path[:-4]
    return rel_path

icon_file = '/home/yezisama/workspace/workflow/EDUagent/frontend/src/components/Icon'

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'material-symbols-outlined' not in content:
        return
        
    def repl(m):
        attrs = m.group(1)
        inner = m.group(2).strip()
        
        if inner.startswith('{') and inner.endswith('}'):
            name_prop = f'name={inner}'
        else:
            name_prop = f'name="{inner}"'
            
        return f'<Icon {name_prop}{attrs}/>'
        
    pattern = r'<span([^>]*material-symbols-outlined[^>]*)>\s*(.*?)\s*</span>'
    new_content, count = re.subn(pattern, repl, content, flags=re.DOTALL)
    
    if count > 0:
        if 'import Icon ' not in new_content:
            rel_import = get_relative_path(file_path, icon_file)
            import_stmt = f"import Icon from '{rel_import}';\n"
            
            last_import_idx = new_content.rfind('import ')
            if last_import_idx == -1:
                new_content = import_stmt + new_content
            else:
                end_of_line = new_content.find('\n', last_import_idx)
                if end_of_line == -1:
                    new_content += '\n' + import_stmt
                else:
                    new_content = new_content[:end_of_line+1] + import_stmt + new_content[end_of_line+1:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file_path} ({count} replacements)")

src_dir = '/home/yezisama/workspace/workflow/EDUagent/frontend/src'
for root, dirs, files in os.walk(src_dir):
    for file in files:
        if file.endswith('.jsx') and file != 'Icon.jsx':
            process_file(os.path.join(root, file))

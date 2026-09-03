import re
from xml.etree import ElementTree as ET

tree = ET.parse('backend/svgs/intl_wintri.svg')
root = tree.getroot()

ns = {'svg': 'http://www.w3.org/2000/svg'}

def inspect_element(el, depth=0):
    tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
    attribs = dict(el.attrib)
    # truncate 'd' attribute
    if 'd' in attribs:
        attribs['d'] = attribs['d'][:60] + '...'
    print('  ' * depth + f"<{tag}> {attribs}")
    if depth < 3:
        for child in el:
            inspect_element(child, depth+1)

inspect_element(root)
print()

# Count paths per group
for g in root:
    tag = g.tag.split('}')[-1] if '}' in g.tag else g.tag
    if tag == 'g':
        gid = g.get('id', 'no-id')
        paths_in_g = [c for c in g if (c.tag.split('}')[-1] if '}' in c.tag else c.tag) == 'path']
        subgroups = [c for c in g if (c.tag.split('}')[-1] if '}' in c.tag else c.tag) == 'g']
        print(f"Group '{gid}': {len(paths_in_g)} direct paths, {len(subgroups)} subgroups")
        for sg in subgroups[:5]:
            sgid = sg.get('id', 'no-id')
            sg_paths = [c for c in sg if (c.tag.split('}')[-1] if '}' in c.tag else c.tag) == 'path']
            print(f"  Subgroup '{sgid}': {len(sg_paths)} paths, attrs={dict(sg.attrib)}")

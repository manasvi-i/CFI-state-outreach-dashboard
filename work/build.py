"""Assemble UPDATED workbook + change_log.csv + needs_review.csv + progress.csv from out/*.csv."""
import csv, glob, collections, sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

W = '/home/user/CFI-state-outreach-dashboard/work/'
OUT = '/home/user/CFI-state-outreach-dashboard/'
rows = list(csv.DictReader(open(W + 'rows_ctx.csv')))
res = {}
WEAK_B = {'151', '349', '350', '355', '395'}
for f in sorted(glob.glob(W + 'out/*.csv')):
    for r in csv.DictReader(open(f)):
        res[r['id']] = r | {'batch': f.split('/')[-1]}

for f in sorted(glob.glob(W + 'out2/*.csv')):
    for r in csv.DictReader(open(f)):
        if r['id'] in res and res[r['id']]['status'].strip().upper() != 'D' and r['status'].strip().upper() == 'D':
            continue  # never let a rerun D downgrade an earlier concrete finding
        res[r['id']] = r | {'batch': 'rerun/' + f.split('/')[-1]}

wb = openpyxl.load_workbook(W + 'input.xlsx')
sheets = {ws.title: ws for ws in wb}
log = []; review = []; counts = collections.defaultdict(collections.Counter)
by_sheet = collections.defaultdict(list)
for r in rows:
    x = res.get(r['id'])
    st = x['status'].strip().upper() if x else 'D'
    if x and r['id'] in WEAK_B and st == 'B':
        st = 'REVIEW'; x = dict(x); x['review_reason'] = 'Agent proposed removal but evidence is undated/weak (' + x['evidence'][:200] + '); kept pending your call'
    note = x['evidence'] if x else 'No result returned by verification batch'
    if not x: x = {k: '' for k in ['new_name','new_designation','successor_name','successor_designation','successor_email','successor_phone','sources','review_reason']}
    sh = r['sheet']
    new_name, new_des = r['name'], r['designation']
    email, phone = r['email'], r['phone']
    action = 'unchanged'
    keep = True
    if st == 'B' or st == 'OFFICE_REMOVED':
        keep = False; action = 'removed'
    elif st in ('C', 'BORDERLINE'):
        if x['new_name']: new_name = x['new_name']
        if x['new_designation']: new_des = x['new_designation']
        action = 'updated' if st == 'C' else 'borderline-kept'
        if (new_name, new_des) == (r['name'], r['designation']) and st == 'C': action = 'unchanged'
    elif st == 'D': action = 'unverified'
    elif st == 'REVIEW': action = 'review-kept'
    if keep:
        by_sheet[sh].append((r, new_name, new_des, email, phone, 'orig'))
    counts[sh][action] += 1
    succ = x['successor_name'].strip()
    if succ:
        by_sheet[sh].append((r, succ, x['successor_designation'], x['successor_email'], x['successor_phone'], 'succ'))
        counts[sh]['successor-added'] += 1
    log.append({'id': r['id'], 'sheet': sh, 'source_row': r['row'], 'state': r['state'], 'district': r['district'],
                'old_name': r['name'], 'old_designation': r['designation'], 'status_code': st, 'action': action,
                'new_name': new_name if keep else '', 'new_designation': new_des if keep else '',
                'successor_name': succ, 'successor_designation': x['successor_designation'] if succ else '',
                'successor_email': x['successor_email'] if succ else '', 'successor_phone': x['successor_phone'] if succ else '',
                'sources': x['sources'], 'evidence': note})
    if st in ('BORDERLINE', 'REVIEW'):
        review.append({'id': r['id'], 'person': r['name'], 'old_post': r['designation'], 'new_post': new_des,
                       'why_ambiguous': x['review_reason'] or note, 'status': 'borderline-kept' if st == 'BORDERLINE' else 'review-kept', 'sources': x['sources']})

# write workbook
arial = Font(name='Arial', size=10)
hdr_font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
fill = PatternFill('solid', fgColor='1F4E78')
side = Side(style='thin', color='BFBFBF')
border = Border(left=side, right=side, top=side, bottom=side)
wrap = Alignment(wrap_text=True, vertical='top')
new = openpyxl.Workbook(); new.remove(new.active)
for title, ws in sheets.items():
    n = new.create_sheet(title)
    for c, h in enumerate(['Name', 'Designation', 'Email', 'Phone Number'], 1):
        cell = n.cell(1, c, h); cell.font = hdr_font; cell.fill = fill; cell.border = border
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    for i, (r, nm, ds, em, ph, kind) in enumerate(by_sheet[title], 2):
        for c, v in enumerate([nm, ds, em, ph], 1):
            cell = n.cell(i, c, v if v != '' else None)
            cell.font = arial; cell.alignment = wrap; cell.border = border
            if c == 4: cell.number_format = '@'
    for col, w in zip('ABCD', (42, 60, 40, 20)): n.column_dimensions[col].width = w
    n.freeze_panes = 'A2'
    n.auto_filter.ref = f'A1:D{n.max_row}'
new.save(OUT + 'CFI_govt_relations_active_engaged_and_target_contacts_UPDATED.xlsx')

def dump(path, data, fields):
    w = csv.DictWriter(open(path, 'w', newline=''), fieldnames=fields); w.writeheader(); w.writerows(data)
dump(OUT + 'change_log.csv', log, list(log[0]))
dump(OUT + 'needs_review.csv', review, ['id', 'person', 'old_post', 'new_post', 'why_ambiguous', 'status', 'sources'])
dump(OUT + 'progress.csv', [{'batch': v['batch'], 'id': k, 'status': v['status']} for k, v in res.items()], ['batch', 'id', 'status'])

print('results for', len(res), 'of', len(rows), 'rows')
for sh, c in counts.items(): print(sh, dict(c))
print('unverified total', sum(c['unverified'] for c in counts.values()))

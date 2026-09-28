"""Сообщение в тему 1206: новые ставки (с проверкой) или тревога рутины."""
import json, os, re, subprocess, urllib.request, urllib.parse

def changed(path):
    out = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'], capture_output=True, text=True).stdout
    return path in out.split() or os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'

def fmt(v):
    return (('%.2f' % v).rstrip('0').rstrip('.')).replace('.', ',')

def check(j):
    bad = []
    if not isinstance(j.get('low'), (int, float)) or not isinstance(j.get('high'), (int, float)):
        return ['low/high не числа']
    if not (5 < j['low'] < j['high'] < 35): bad.append('нужно 5 < low < high < 35')
    if not re.fullmatch(r'\d{4}-\d\d-\d\d', str(j.get('date', ''))): bad.append('date не ГГГГ-ММ-ДД')
    return bad

msgs = []
if os.path.exists('trevoga.txt') and changed('trevoga.txt'):
    msgs.append('⚠️ Ставки для квизов НЕ обновлены\n\n' + open('trevoga.txt', encoding='utf-8').read().strip()
                + '\n\nНа сайте остались прежние ставки — квизы работают.')
if changed('rates.json'):
    j = json.load(open('rates.json', encoding='utf-8'))
    bad = check(j)
    d = '.'.join(reversed(str(j.get('date', '')).split('-')))
    if bad:
        msgs.append('⛔ rates.json не прошёл проверку: ' + '; '.join(bad)
                    + '\nКвизы такой файл отбросят и покажут запасные ставки из блока. Нужна правка.')
    else:
        prev = subprocess.run(['git', 'show', 'HEAD~1:rates.json'], capture_output=True, text=True).stdout
        was = ''
        try:
            p = json.loads(prev)
            if (p['low'], p['high'], p['date']) != (j['low'], j['high'], j['date']):
                was = '\nБыло: %s–%s%% на %s' % (fmt(p['low']), fmt(p['high']), '.'.join(reversed(p['date'].split('-'))))
        except Exception:
            pass
        msgs.append('✅ Ставки в квизах обновлены\n\nВилка: %s–%s%% (ДОМ.РФ на %s)%s\n'
                    'Квизы ипотеки, рефинансирования и новостроек на главной подхватят её сами.'
                    % (fmt(j['low']), fmt(j['high']), d, was)
                    + ('\n\n' + j['note'] if j.get('note') else ''))

tok, chat, topic = os.environ.get('TOKEN'), os.environ.get('CHAT'), os.environ.get('TOPIC')
for m in msgs:
    print(m)
    if not tok:
        raise SystemExit('нет секрета STAVKI_BOT_TOKEN')
    data = urllib.parse.urlencode({'chat_id': chat, 'message_thread_id': topic, 'text': m}).encode()
    r = json.load(urllib.request.urlopen('https://api.telegram.org/bot%s/sendMessage' % tok, data))
    assert r.get('ok'), r

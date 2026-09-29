"""Читает свежий «Обзор ставок по ипотеке в банках» СПРОСИ.ДОМ.РФ и обновляет rates.json.

Нижняя — первый крупный банк в списке «Минимальные ставки», верхняя — средневзвешенная
по вторичке. Любое сомнение → rates.json не трогаем, пишем trevoga.txt (решение Елены:
старые ставки лучше неверных; квиз сам спрячет цифры, когда ставкам больше 35 дней).
Запуск без аргументов; --proverka ФАЙЛ.html — только разобрать сохранённую страницу.
"""
import datetime as dt, html, json, os, re, sys, urllib.request

BASE = 'https://xn--h1alcedd.xn--d1aqf.xn--p1ai/news/obzor-stavok-po-ipoteke-v-bankakh-na-%d-%s-%d-goda/'
MES = ['yanvarya', 'fevralya', 'marta', 'aprelya', 'maya', 'iyunya', 'iyulya', 'avgusta',
       'sentyabrya', 'oktyabrya', 'noyabrya', 'dekabrya']
MES_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа',
          'сентября', 'октября', 'ноября', 'декабря']
# Крупные банки (по подстроке в нижнем регистре). Мелкие региональные в нижнюю не берём.
KRUPNYE = ['сбер', 'втб', 'альфа', 'т-банк', 'т‑банк', 'тинькофф', 'газпромбанк', 'дом.рф', 'совкомбанк',
           'россельхозбанк', 'псб', 'промсвязьбанк', 'райффайзен', 'мкб', 'московский кредитный',
           'росбанк', 'уралсиб', 'санкт-петербург', 'ак барс', 'почта банк']
MAX_SKACHOK = 3.0


def tekst(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                               'AppleWebKit/537.36 Chrome/128 Safari/537.36'})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode('utf-8', 'replace')
    except Exception:
        return None


def chistyy(h):
    h = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', h)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h)))


def num(s):
    return float(s.replace(',', '.'))


def razobrat(t):
    """-> dict или строка с причиной, почему разобрать нельзя."""
    m = re.search(r'Обзор ставок по ипотеке в банках на (\d{1,2}) (\w+) (\d{4}) года', t)
    if not m or m.group(2) not in MES_RU:
        return 'не нашёл заголовок «Обзор ставок … на <дата> года»'
    date = dt.date(int(m.group(3)), MES_RU.index(m.group(2)) + 1, int(m.group(1)))
    # вторичка: «18,67% на вторичном» (с 16.09.2026) или «вторичный рынок — 18,68%» (2 и 9.09.2026)
    h = re.search(r'(\d{1,2},\d{1,2})\s*% на вторичном', t) or re.search(r'вторичный рынок\s*—\s*(\d{1,2},\d{1,2})\s*%', t)
    if not h:
        return 'не нашёл средневзвешенную ставку по вторичке'
    r = {'high': num(h.group(1)), 'date': date.isoformat(), 'low': None, 'lowBank': None, 'spisok': []}
    # «Минимальные ставки:» или «…минимальные ставки на покупку квартиры:», конец — «Максимальные ставки»
    m = re.search(r'[Мм]инимальные ставки[^:.]{0,40}:', t)
    j = t.find('Максимальные ставки', m.end()) if m else -1
    if not m or j < 0:
        return r   # списка в тексте нет (16.09.2026 он был только картинкой) — нижняя останется прежней
    spisok = re.findall(r'([^—%:]+?)\s+—\s+(\d{1,2}(?:,\d{1,2})?)\s*%', t[m.end():j])
    r['spisok'] = [(b.strip(), num(v)) for b, v in spisok]
    if not r['spisok']:
        return 'список минимальных ставок есть, но в новом формате — не разобрал'
    krup = [(b, v) for b, v in r['spisok'] if any(k in b.lower() for k in KRUPNYE)]
    if not krup:
        return 'в минимальных ставках нет ни одного крупного банка: ' + '; '.join('%s — %s%%' % (b, fmt(v)) for b, v in r['spisok'])
    r['low'], r['lowBank'] = krup[0][1], krup[0][0]
    return r


def fmt(v):
    return (('%.2f' % v).rstrip('0').rstrip('.')).replace('.', ',')


def trevoga(sreda, prichina, nashel, url):
    kl = 'Неделя обзора: %s\nПричина: %s\n' % (sreda.strftime('%d.%m.%Y'), prichina)
    try:
        if open('trevoga.txt', encoding='utf-8').read().startswith(kl):
            print('тревога уже отправлена на этой неделе:', prichina)
            return
    except FileNotFoundError:
        pass
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).strftime('%d.%m.%Y %H:%M мск')
    open('trevoga.txt', 'w', encoding='utf-8').write(kl + 'Нашёл: %s\nИсточник: %s\nПроверено: %s\n'
                                                      % (nashel, url or 'не найден', now))
    print('ТРЕВОГА:', prichina)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--proverka':
        print(razobrat(chistyy(open(sys.argv[2], encoding='utf-8').read())))
        return
    segodnya = (dt.datetime.utcnow() + dt.timedelta(hours=3)).date()
    if os.environ.get('SEGODNYA'):   # только для проверок: подменить «сегодня»
        segodnya = dt.date.fromisoformat(os.environ['SEGODNYA'])
    sreda = segodnya - dt.timedelta(days=(segodnya.weekday() - 2) % 7)   # последняя среда ≤ сегодня
    tek = json.load(open('rates.json', encoding='utf-8'))
    if tek['date'] >= sreda.isoformat():
        print('уже обновлено на', tek['date']); return

    url = r = None
    for d in (sreda, sreda - dt.timedelta(days=1), sreda + dt.timedelta(days=1)):
        if d > segodnya:
            continue
        u = BASE % (d.day, MES[d.month - 1], d.year)
        h = tekst(u)
        if h and 'Обзор ставок по ипотеке в банках на' in h:
            url, r = u, razobrat(chistyy(h))
            break
    if url is None:
        if segodnya == sreda:
            print('обзора на', sreda, 'пока нет — сегодня среда, попробую позже'); return
        return trevoga(sreda, 'обзор ДОМ.РФ за неделю не найден', 'ничего', None)
    if isinstance(r, str):
        return trevoga(sreda, 'статью не удалось разобрать — ' + r, 'страница открылась', url)

    note = ''
    if r['low'] is None:   # списка банков в тексте нет — нижнюю не выдумываем, держим прежнюю
        r['low'], r['lowBank'] = tek['low'], 'прежняя'
        note = ('Списка банков в тексте обзора нет (только картинка) — нижняя оставлена прежней, %s%%. '
                'Верхняя обновлена по обзору.' % fmt(tek['low']))
    nashel = 'нижняя %s%% (%s), верхняя %s%% (вторичка), на %s' % (fmt(r['low']), r['lowBank'], fmt(r['high']), r['date'])
    bad = []
    if not (5 < r['low'] < r['high'] < 35):
        bad.append('нужно 5 < нижняя < верхняя < 35')
    for k, nm in (('low', 'нижняя'), ('high', 'верхняя')):
        if abs(r[k] - tek[k]) > MAX_SKACHOK:
            bad.append('%s прыгнула на %s п.п. (было %s%%)' % (nm, fmt(abs(r[k] - tek[k])), fmt(tek[k])))
    if not (tek['date'] < r['date'] <= segodnya.isoformat()):
        bad.append('дата обзора %s не новее %s или в будущем' % (r['date'], tek['date']))
    if bad:
        return trevoga(sreda, 'проверка правдоподобия не пройдена: ' + '; '.join(bad), nashel, url)

    novye = {'low': r['low'], 'high': r['high'], 'date': r['date'], 'src': 'ДОМ.РФ'}
    open('rates.json', 'w', encoding='utf-8').write(json.dumps(novye, ensure_ascii=False, separators=(',', ':')) + '\n')
    if note:
        novye['note'] = note   # квизы лишнее поле не читают; отчёт покажет его Елене
        open('rates.json', 'w', encoding='utf-8').write(json.dumps(novye, ensure_ascii=False, separators=(',', ':')) + '\n')
    ist = dict(novye, lowBank=r['lowBank'], url=url, minimalnye=['%s — %s%%' % (b, fmt(v)) for b, v in r['spisok']])
    open('istoriya/%s.json' % r['date'], 'w', encoding='utf-8').write(json.dumps(ist, ensure_ascii=False, indent=1) + '\n')
    print('ОБНОВЛЕНО:', nashel)


if __name__ == '__main__':
    main()

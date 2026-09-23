"""Read-only, printable client report and paginated PDF from analytical snapshots."""
import argparse
from datetime import datetime
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import threading
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.packages'))
LABELS=dict(consolidator='Сборщик',transit='Транзит',distributor='Распределитель',
            terminal='Конечный получатель (в выборке)',coordinator='Координатор',peripheral='Периферия / недостаточно данных')
FONT_LOCK=threading.Lock()
LIMITS='Роль - гипотеза для проверки, не утверждение о виновности. Сила правила не является вероятностью. Входящие seed неполны; наблюдение ограничено четвёртым шагом, внутрибанковскими переводами и порогом 5 000 KZT. Точное время и назначение платежей неизвестны.'


def number(value):
    return f'{value:,.2f}'.replace(',',' ').replace('.',',')


def load_report(root,gid):
    if not gid or not gid.isascii() or not gid.isdecimal() or len(gid)>19:
        raise ValueError('Некорректный gid')
    raw=(root/'out/dashboard.json').read_bytes()
    data=json.loads(raw)
    node=next((n for n in data['nodes'] if str(n['gid'])==gid),None)
    if node is None:raise ValueError('Клиент отсутствует в текущей выборке')
    weekly=[]
    weekly_path=root/'out/weekly.json'
    weekly_note='Недельный расчёт отсутствует. Выполните python weekly_analytics.py.'
    if weekly_path.exists():
        report=json.loads(weekly_path.read_text(encoding='utf-8'))
        if report['start']==data['summary']['start'] and report['end']==data['summary']['end']:
            weekly_note='Суммы за наблюдаемые дни; среднее делится на календарные дни, включая дни без операций. Активность = вход + выход, самоперевод считается один раз. Контрагенты уникальны в пределах недели.'
            for week in report['weeks']:
                n=week['clients'].get(gid,{'amount_tiyn':0,'n_tx':0,'peers':[]})
                weekly.append([week['start']+' - '+week['end'],str(week['days'])+(' *' if week['partial'] else ''),
                    number(n['amount_tiyn']/100),number(n['amount_tiyn']/100/week['days']),str(n['n_tx']),str(len(n['peers']))])
        else:weekly_note='Недельный расчёт относится к другому периоду и не включён. Пересчитайте python run.py.'
    request=('Продолжение исходящих переводов за четвёртым шагом и операции вне выборки.' if node['truncated_by_depth']
             else 'Полную историю входящих seed, остатки и назначения платежей.' if node['is_seed']
             else 'Точное время и назначение платежей, остатки на счёте, полные входящие и исходящие за пределами выборки.')
    return dict(gid=gid,node=node,summary=data['summary'],created=datetime.now().astimezone().isoformat(timespec='seconds'),
        snapshot=sha256(raw).hexdigest()[:16],weekly=weekly,weekly_note=weekly_note,request=request,
        edges=sorted([e for e in data['edges'] if str(e['src'])==gid or str(e['dst'])==gid],key=lambda e:-e['sum_kzt']),
        temporal=sorted([m for m in data['temporal_matches'] if str(m['gid'])==gid],key=lambda m:(m['in_date'],m['out_date'])))


def sections(r):
    n=r['node']
    facts=[['Роль',LABELS[n['role']]],['Приоритет проверки',f"{n['priority_score']:.6f}"],
        ['Сила правила / устойчивость',f"{n['role_score']:.2f} / {n['role_stability']:.0%} (три настройки порогов)"],
        ['Вход / выход, KZT',number(n['in_kzt'])+' / '+number(n['out_kzt'])],
        ['Входящих / исходящих операций',f"{n['in_tx']} / {n['out_tx']}"],
        ['Контрагентов на вход / выход',f"{n['in_deg']} / {n['out_deg']}"],
        ['Группа / глубина / seed',f"{n['cluster_id']} / {n['depth']} / {'да' if n['is_seed'] else 'нет'}"],
        ['Граница наблюдения','да' if n['truncated_by_depth'] else 'нет'],
        ['Достижимость / внешние группы',f"От {n['seed_reach']} seed / {n['neighbor_clusters']} групп"]]
    windows=[[m['in_date'],m['out_date'],str(m['lag_days']),number(m['amount_tiyn']/100)] for m in r['temporal']]
    edges=[[str(e['src']),str(e['dst']),number(e['sum_kzt']),str(e['n_tx'])] for e in r['edges']]
    return facts,windows,edges


def html_report(r):
    facts,windows,edges=sections(r)
    def table(headers,rows):
        return '<div class="report-table"><table><thead><tr>'+''.join('<th>'+escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+(''.join('<tr>'+''.join('<td>'+escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows) or '<tr><td colspan="'+str(len(headers))+'">Нет наблюдаемых данных</td></tr>')+'</tbody></table></div>'
    n=r['node'];gid=r['gid']
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Поток - отчёт {gid}</title><style>
    body{{font:14px/1.6 "Segoe UI",Arial,sans-serif;margin:0;color:#18273b;background:#eaf0f5}}main{{max-width:980px;margin:24px auto;background:white;padding:36px;border-radius:12px}}h1{{font-size:26px;overflow-wrap:anywhere}}h2{{font-size:18px;margin-top:30px;border-bottom:2px solid #23846e;padding-bottom:8px}}.meta{{color:#536477;font-size:12px;overflow-wrap:anywhere}}nav{{display:flex;flex-wrap:wrap;gap:14px}}a,button{{display:inline-block;padding:10px 14px;border:1px solid #237f6c;border-radius:6px;color:#155d4f;background:white;text-decoration:none;cursor:pointer;font:inherit}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #d9e2eb;vertical-align:top}}th{{background:#eef4f6}}.report-table{{overflow:auto}}.notice{{background:#f3f7f7;border-left:3px solid #23846e;padding:14px}}@page{{size:A4;margin:16mm}}@media print{{body{{background:white;font-size:11px}}main{{margin:0;padding:0;max-width:none}}nav{{display:none}}h2{{break-after:avoid}}tr{{break-inside:avoid}}thead{{display:table-header-group}}.report-table{{overflow:visible}}a{{border:0}}}}
    </style></head><body><main><nav><a href="/analytics?gid={gid}">Назад к клиенту</a><a href="/download/client.pdf?gid={gid}">Скачать PDF</a><button onclick="window.print()">Печать</button></nav>
    <h1>Отчёт по клиенту {gid}</h1><p class="meta">Период: {r['summary']['start']} - {r['summary']['end']} · Сформирован: {r['created']}<br>Снимок расчёта: {r['snapshot']} · Обезличенный gid</p>
    <p class="notice">{escape(LIMITS)}</p><h2>Показатели клиента</h2>{table(['Показатель','Значение'],facts)}
    <h2>Основания роли и приоритета</h2><p><b>Роль:</b> {escape(n['evidence'])}</p><p><b>Приоритет:</b> {escape(n['priority_evidence'])}</p>
    <h2>Следующий запрос данных</h2><p>{escape(r['request'])}</p>
    <h2>Недельная динамика</h2><p>{escape(r['weekly_note'])}</p>{table(['Период','Дней*','Активность, KZT','KZT / день','Операций','Контрагентов'],r['weekly'])}<p class="meta">* Неполная календарная неделя. Нулевое значение означает отсутствие операций в выборке.</p>
    <h2>Возможный транзит за 1-2 дня</h2><p>FIFO-сценарий: {number(n['fast_matched_kzt'])} KZT, {n['fast_share']:.1%} входа. Это возможное сопоставление сумм, не доказанное движение тех же денег. Порядок внутри дня неизвестен.</p>{table(['Вход','Выход','Дней','Сопоставлено, KZT'],windows)}
    <h2>Все прямые связи ({len(edges)})</h2><p>Направление: отправитель → получатель. Суммы агрегированы за весь период.</p>{table(['Отправитель','Получатель','Сумма, KZT','Операций'],edges)}
    <p class="meta">Источник: предоставленные Parquet, локальный аналитический расчёт. Справка не заменяет проверку первичных операций.</p></main></body></html>'''


def pdf_report(r):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    candidates=[(Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
        (Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'))]
    fonts=next(((a,b) for a,b in candidates if a.exists() and b.exists()),None)
    if fonts is None:raise RuntimeError('Для PDF установите Arial или DejaVu Sans с кириллицей; доступна версия для печати.')
    with FONT_LOCK:
        if 'Potok' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('Potok',str(fonts[0])))
            pdfmetrics.registerFont(TTFont('PotokBold',str(fonts[1])))
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyRU',fontName='Potok',fontSize=9,leading=13,spaceAfter=8))
    styles.add(ParagraphStyle(name='HeadRU',fontName='PotokBold',fontSize=14,leading=18,spaceBefore=12,spaceAfter=10,keepWithNext=True))
    styles.add(ParagraphStyle(name='TitleRU',fontName='PotokBold',fontSize=20,leading=25,spaceAfter=15))
    styles.add(ParagraphStyle(name='CellRU',fontName='Potok',fontSize=8,leading=11))
    p=lambda text,style='BodyRU':Paragraph(escape(str(text)),styles[style])
    buffer=BytesIO();doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=42,bottomMargin=42,
        title='Поток - клиент '+r['gid'],author='Поток - локальная аналитика')
    story=[]
    def heading(t):story.append(p(t,'HeadRU'))
    def table(headers,rows,widths):
        cells=[[p(x,'CellRU') for x in headers]]+[[p(x,'CellRU') for x in row] for row in rows]
        if not rows:cells.append([p('Нет наблюдаемых данных','CellRU')]+['']*(len(headers)-1))
        t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e3f1ed')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#d3dfe5')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.extend([t,Spacer(1,10)])
    facts,windows,edges=sections(r);n=r['node']
    story += [p('ПОТОК / АНАЛИТИЧЕСКАЯ СПРАВКА','HeadRU'),p('Клиент '+r['gid'],'TitleRU'),
        p(f"Период: {r['summary']['start']} - {r['summary']['end']}. Сформирован: {r['created']}. Снимок: {r['snapshot']}."),p(LIMITS)]
    table(['Показатель','Значение'],facts,[220,295])
    heading('Основания роли и приоритета');story += [p(n['evidence']),p(n['priority_evidence'])]
    heading('Следующий запрос данных');story.append(p(r['request']))
    story.append(PageBreak());heading('Недельная динамика');story.append(p(r['weekly_note']))
    table(['Период','Дней*','Активность, KZT','KZT / день','Операций','Контрагентов'],r['weekly'],[125,35,105,100,65,85])
    story.append(p('* Неполная календарная неделя. Ноль означает отсутствие наблюдаемых операций.'))
    heading('Возможный транзит за 1-2 дня');story.append(p(f"Сопоставлено {number(n['fast_matched_kzt'])} KZT ({n['fast_share']:.1%} входа). FIFO - возможное распределение сумм, не доказанная трассировка денег. Последние два дня периода ограничивают наблюдение."))
    table(['Вход','Выход','Дней','Сопоставлено, KZT'],windows,[130,130,65,190])
    story.append(PageBreak());heading(f"Все прямые связи ({len(edges)})")
    story.append(p('Направление: отправитель -> получатель. Агрегированные суммы за весь период; каждая направленная пара показана один раз.'))
    table(['Отправитель','Получатель','Сумма, KZT','Операций'],edges,[150,150,145,70])
    story.append(p('Источник: предоставленные Parquet и локальный аналитический расчёт. Справка не заменяет проверку первичных операций.'))
    def footer(canvas,doc):
        canvas.setFont('Potok',8);canvas.setFillColor(colors.HexColor('#536477'))
        canvas.drawString(40,23,'ПОТОК | '+r['gid']);canvas.drawRightString(A4[0]-40,23,'Страница '+str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--gid',required=True);parser.add_argument('--out',type=Path)
    args=parser.parse_args();report=load_report(ROOT,args.gid)
    target=args.out or ROOT/'output/pdf'/('client-'+args.gid+'.pdf')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(pdf_report(report));print(target)

"""English, Norwegian Bokmål and Russian text and formatting for the dashboard."""
import base64
from decimal import Decimal

LANGUAGES = {"en": "English", "nb": "Norsk", "ru": "Русский"}
TEXT = {
    "title": ("Currency overview", "Valutaoversikt"),
    "kyiv": ("Kyiv", "Kyiv"),
    "oslo": ("Oslo", "Oslo"),
    "intro": ("Dollar, euro, Scandinavian currencies and hryvnia — in one place.", "Dollar, euro, skandinaviske valutaer og hryvnia — samlet på ett sted."),
    "refresh": ("Update rates", "Oppdater kurser"),
    "loading": ("Fetching official rates from Norges Bank and NBU…", "Henter offisielle kurser fra Norges Bank og NBU…"),
    "updated": ("Rates and history updated", "Kurser og historikk er oppdatert"),
    "read_error": ("Could not read the saved history. Check access to the data folder.", "Kunne ikke lese lagret historikk. Kontroller tilgangen til datamappen."),
    "refresh_error": ("Could not complete the update. Saved values are shown with their actual dates.", "Oppdateringen kunne ikke fullføres. Lagrede verdier vises med sine faktiske datoer."),
    "error_api": ("The rate source is unavailable. Check your connection and try again.", "Kurskilden er utilgjengelig. Kontroller tilkoblingen og prøv igjen."),
    "error_data": ("The source returned invalid or incomplete data; those values were not imported.", "Kilden returnerte ugyldige eller ufullstendige data. Disse verdiene ble ikke importert."),
    "error_storage": ("Could not save or read local files. Check access to the data folder.", "Kunne ikke lagre eller lese lokale filer. Kontroller tilgangen til datamappen."),
    "error_nbu": ("Norges Bank was updated, but NBU could not be updated. Previous NOK/UAH values are retained.", "Norges Bank er oppdatert, men NBU kunne ikke oppdateres. Tidligere NOK/UAH-verdier er beholdt."),
    "empty": ("Select ‘Update rates’ to download the rate history.", "Velg «Oppdater kurser» for å laste ned kurshistorikken."),
    "unknown": ("unknown", "ukjent"),
    "latest_date": ("Latest rate date: {date}", "Siste kursdato: {date}"),
    "loaded": ("Loaded: {stamp} · Oslo", "Lastet inn: {stamp} · Oslo"),
    "changes_note": ("Changes are relative to the previous published observation", "Endringer er i forhold til forrige publiserte observasjon"),
    "old_data": ("The latest rate is more than four days old. Update rates to check the source.", "Siste kurs er mer enn fire dager gammel. Oppdater kursene for å kontrollere kilden."),
    "no_today": ("No observation for {date} is saved yet. Cards show the actual rate date.", "Ingen observasjon for {date} er lagret ennå. Kortene viser den faktiske kursdatoen."),
    "no_data": ("no data", "ingen data"),
    "unit": ("{quote} per 1 {base}", "{quote} per 1 {base}"),
    "delta_description": ("{unit} vs previous publication", "{unit} mot forrige publisering"),
    "mini_alt": ("{pair}: latest {count} observations; hover for date and rate", "{pair}: siste {count} observasjoner; hold pekeren over for dato og kurs"),
    "mini_period": ("Latest {count} observations · {start}–{end}", "Siste {count} observasjoner · {start}–{end}"),
    "compared_with": ("Compared with {date}", "Sammenlignet med {date}"),
    "no_previous": ("No previous observation", "Ingen tidligere observasjon"),
    "nbu_caption": ("Source: NBU · Effective date", "Kilde: NBU · Gyldighetsdato"),
    "mini_note": ("Mini charts show the latest 7 published observations. Hover anywhere on a chart for the date and rate. The arrow and percentage compare only with the previous observation. Each card has its own scale.", "Minigrafene viser de siste 7 publiserte observasjonene. Hold pekeren over grafen for å se dato og kurs. Pil og prosent sammenligner bare med forrige observasjon. Hvert kort har sin egen skala."),
    "trend": ("Exchange rate trend", "Kursutvikling"),
    "pair": ("Currency pair", "Valutapar"),
    "period": ("Period", "Periode"),
    "period_1m": ("1 month", "1 md."),
    "period_3m": ("3 months", "3 md."),
    "period_1y": ("1 year", "1 år"),
    "period_3y": ("3 years", "3 år"),
    "compare": ("Compare all pairs in percent", "Sammenlign alle par i prosent"),
    "view": ("Chart view", "Grafvisning"),
    "view_rate": ("Rate", "Kurs"),
    "view_percent": ("Change, %", "Endring, %"),
    "comparison_alt": ("Percentage change of five currency pairs from a shared baseline date", "Prosentvis endring for fem valutapar fra en felles startdato"),
    "baseline": ("Shared baseline: {date} = 0%. Missing values are not filled.", "Felles utgangspunkt: {date} = 0 %. Manglende verdier fylles ikke inn."),
    "no_common": ("No shared date for all five pairs in this period. Update the history.", "Ingen felles dato for alle fem par i denne perioden. Oppdater historikken."),
    "quote_alt": ("{view} for {pair} in the selected period; the scale follows the data range", "{view} for {pair} i valgt periode; skalaen følger dataintervallet"),
    "range": ("Minimum: {low_date} — {low} · Maximum: {high_date} — {high} · Period change: {change}%", "Minimum: {low_date} — {low} · Maksimum: {high_date} — {high} · Endring i perioden: {change} %"),
    "percent_note": ("Change relative to {date} (0%). The Y axis is in percent.", "Endring i forhold til {date} (0 %). Y-aksen viser prosent."),
    "scale_note": ("Automatic scale follows the selected data range, rather than starting at zero. It adjusts to updated rates, pair and period changes, including sharp movements. Quote units stay the same.", "Automatisk skala følger det valgte dataintervallet i stedet for å starte på null. Den tilpasses oppdaterte kurser, bytte av par og periode, også ved store utslag. Kursenhetene er uendret."),
    "published_period": ("{start} — {end} · Published observations only", "{start} — {end} · Kun publiserte observasjoner"),
    "empty_period": ("No saved observations in this period. Update the history or select another period.", "Ingen lagrede observasjoner i denne perioden. Oppdater historikken eller velg en annen periode."),
    "horizontal_note": ("Published dates are equally spaced, without empty weekend slots. Hover between or above points to see the nearest date and value.", "Publiserte datoer har lik avstand, uten tomme plasser for helger. Hold pekeren mellom eller over punktene for å se nærmeste dato og verdi."),
    "converter": ("Currency converter", "Valutakalkulator"),
    "latest_published": ("Using the latest published rate", "Med siste publiserte kurs"),
    "direction": ("Direction", "Retning"),
    "convert_from": ("From", "Fra"),
    "convert_to": ("To", "Til"),
    "reverse": ("Reverse direction", "Omvendt retning"),
    "amount": ("Amount in {code}", "Beløp i {code}"),
    "receive": ("You receive, {code}", "Du får, {code}"),
    "converter_note": ("Rate dated {date}. Bank fees and markups are not included.", "Kurs datert {date}. Bankgebyrer og påslag er ikke inkludert."),
    "empty_pair": ("No data for this pair yet.", "Ingen data for dette paret ennå."),
    "week_title": ("Last 10 business days", "Siste 10 virkedager"),
    "publication_title": ("Exchange rate updates:", "Oppdatering av valutakurser:"),
    "week_note": ("Monday–Friday · Quote currency per one unit of the base currency", "Mandag–fredag · Kurs i valutaen til høyre per én enhet av valutaen til venstre"),
    "publication_nb": ("Norges Bank: around 16:00 Oslo time on business days (USD/NOK, EUR/NOK, USD/EUR, NOK/SEK).", "Norges Bank: rundt kl. 16.00 Oslo-tid på virkedager (USD/NOK, EUR/NOK, USD/EUR, NOK/SEK)."),
    "publication_nbu": ("NBU: by 15:30 Kyiv time on the setting day (NOK/UAH). The rate takes effect on the next business day.", "NBU: senest kl. 15.30 Kyiv-tid på fastsettelsesdagen (NOK/UAH). Kursen gjelder fra neste virkedag."),
    "publication_refresh": ("After publication, select ‘Update rates’ to load the new values. Successful checks are shared for 5 minutes.", "Velg «Oppdater kurser» etter publisering for å hente de nye verdiene. Vellykkede kontroller deles i 5 minutter."),
    "download": ("Download CSV", "Last ned CSV"),
    "date": ("Date", "Dato"),
    "table_alt": ("Five currency pairs over the last ten business days; a dash means no saved value", "Fem valutapar de siste ti virkedagene; en strek betyr at ingen verdi er lagret"),
    "missing_note": ("— No value is saved for this date. Select ‘Update rates’ to check publication.", "— Ingen verdi er lagret for denne datoen. Velg «Oppdater kurser» for å kontrollere publiseringen."),
    "download_all": ("Download full saved history as CSV", "Last ned hele den lagrede historikken som CSV"),
    "sources": ("Sources and calculations", "Kilder og beregninger"),
    "source_nb": ("Source: [official Norges Bank API](https://www.norges-bank.no/en/topics/Statistics/exchange_rates/). USD/EUR = USD/NOK ÷ EUR/NOK on the same date. NOK/SEK is SEK per 1 NOK; the quote per 100 SEK is normalized before inversion. Changes compare with the previous published observation. Missing weekend and holiday rates are not filled in.", "Kilde: [Norges Banks offisielle API](https://www.norges-bank.no/en/topics/Statistics/exchange_rates/). USD/EUR = USD/NOK ÷ EUR/NOK på samme dato. NOK/SEK er SEK per 1 NOK; noteringen per 100 SEK normaliseres før den inverteres. Endringer sammenlignes med forrige publiserte observasjon. Manglende kurser for helger og helligdager fylles ikke inn."),
    "source_nbu": ("NOK/UAH uses the [official NBU rate](https://bank.gov.ua/ua/markets/exchangerates), UAH per 1 NOK. NBU effective dates may differ from Norges Bank publication dates. No cross-rate is calculated between different sources.", "NOK/UAH bruker [NBUs offisielle kurs](https://bank.gov.ua/ua/markets/exchangerates), UAH per 1 NOK. NBUs gyldighetsdatoer kan avvike fra Norges Banks publiseringsdatoer. Det beregnes ingen krysskurs mellom ulike kilder."),
    "saved_note": ("History loads automatically on first use. Rate checks are shared for 5 minutes after a successful update. After an error, retry after 30 seconds.", "Historikken lastes automatisk ved første bruk. Kurskontroller deles i 5 minutter etter en vellykket oppdatering. Prøv igjen etter 30 sekunder ved feil."),
    "project_folder": ("Application folder: {path}", "Programmappe: {path}"),
    "footer": ("Fjord FX · 5 pairs · Norges Bank + NBU · Europe/Oslo", "Fjord FX · 5 par · Norges Bank + NBU · Europe/Oslo"),
    "period_change": ("Period change", "Endring i perioden"),
    "percent_axis": ("Change from start of period, %", "Endring fra periodens start, %"),
    "show_mini": ("Show mini charts", "Vis minigrafer"),
    "chart_help": ("How to read the charts", "Slik leser du grafene"),
    "table_scroll": ("Scroll sideways to see all pairs. The date stays visible.",
                     "Rull sidelengs for å se alle par. Datoen forblir synlig."),
    "amount_help": ("Use a decimal point when entering an amount. Press Enter or leave the field to apply it.",
                    "Bruk punktum som desimaltegn ved inntasting. Trykk Enter eller gå ut av feltet for å bruke beløpet."),
}

RUSSIAN = {'title': 'Валютный обзор',
 'kyiv': 'Киев',
 'oslo': 'Осло',
 'intro': 'Доллар, евро, скандинавские кроны и гривна — в одном месте.',
 'refresh': 'Обновить курсы',
 'loading': 'Получаем официальные курсы Norges Bank и НБУ…',
 'updated': 'Курсы и история обновлены',
 'read_error': 'Не удалось прочитать сохранённую историю. Проверьте доступ к папке data.',
 'refresh_error': 'Не удалось завершить обновление. Показаны сохранённые значения с их фактическими датами.',
 'error_api': 'Источник курсов недоступен. Проверьте соединение и повторите попытку.',
 'error_data': 'Источник вернул неверные или неполные данные. Эти значения не были импортированы.',
 'error_storage': 'Не удалось сохранить или прочитать локальные файлы. Проверьте доступ к папке data.',
 'error_nbu': 'Norges Bank обновлён, но НБУ недоступен. Предыдущие значения NOK/UAH сохранены.',
 'empty': 'Нажмите «Обновить курсы», чтобы загрузить историю.',
 'unknown': 'неизвестно',
 'latest_date': 'Последняя дата курса: {date}',
 'loaded': 'Загружено: {stamp} · Осло',
 'changes_note': 'Изменения — к предыдущей опубликованной дате',
 'old_data': 'Последний курс старше четырёх дней. Обновите курсы, чтобы проверить источник.',
 'no_today': 'За {date} в сохранённой истории пока нет значения. Карточки показывают фактическую дату курса.',
 'no_data': 'нет данных',
 'unit': '{quote} за 1 {base}',
 'delta_description': '{unit} к предыдущей публикации',
 'mini_alt': '{pair}: последние {count} значений; дата и курс при наведении',
 'mini_period': 'Последние {count} значений · {start}–{end}',
 'compared_with': 'Сравнение с {date}',
 'no_previous': 'Нет предыдущей публикации',
 'nbu_caption': 'Источник: НБУ · Дата действия курса',
 'mini_note': 'Мини-графики показывают последние 7 опубликованных значений. Наведите мышь в любую часть '
              'графика, чтобы увидеть дату и курс. Стрелка и процент — только к предыдущей дате курса. У '
              'каждой карточки своя шкала.',
 'trend': 'Динамика курса',
 'pair': 'Валютная пара',
 'period': 'Период',
 'period_1m': '1 мес.',
 'period_3m': '3 мес.',
 'period_1y': '1 год',
 'period_3y': '3 года',
 'compare': 'Сравнить все пары в процентах',
 'view': 'Вид графика',
 'view_rate': 'Курс',
 'view_percent': 'Изменение, %',
 'comparison_alt': 'Процентное изменение пяти валютных пар от общей начальной даты',
 'baseline': 'Общая база сравнения: {date} = 0%. Пропуски не заполняются.',
 'no_common': 'В выбранном периоде пока нет общей даты для всех пяти пар. Обновите историю.',
 'quote_alt': '{view} {pair} за выбранный период; шкала по диапазону наблюдений',
 'range': 'Минимум: {low_date} — {low} · Максимум: {high_date} — {high} · За период: {change}%',
 'percent_note': 'Изменение относительно {date} (0%). Единица оси Y — проценты.',
 'scale_note': 'Автоматическая шкала по диапазону периода, не от нуля: пересчитывается при обновлении '
               'курсов, смене пары и периода, включая резкие изменения. Единицы курса не изменены.',
 'published_period': '{start} — {end} · Только опубликованные значения',
 'empty_period': 'В этом периоде нет сохранённых значений. Обновите историю или выберите другой период.',
 'horizontal_note': 'По горизонтали — даты опубликованных значений с равными интервалами, без пустых мест за '
                    'выходные. Наведите мышь между точками или над ними: подсказка покажет ближайшую дату и '
                    'значение.',
 'converter': 'Конвертер',
 'latest_published': 'По последнему опубликованному курсу',
 'direction': 'Направление',
 'convert_from': 'Из валюты',
 'convert_to': 'В валюту',
 'reverse': 'Обратное направление',
 'amount': 'Сумма в {code}',
 'receive': 'Вы получите, {code}',
 'converter_note': 'Курс от {date}. Комиссии и наценки банка не учтены.',
 'empty_pair': 'Для этой пары пока нет данных.',
 'week_title': 'Последние 10 рабочих дней',
 'publication_title': 'Обновление курсов валют:',
 'week_note': 'Понедельник–пятница · Курс в валюте справа за одну единицу валюты слева',
 'publication_nb': 'Norges Bank: около 16:00 по времени Осло в рабочие дни (USD/NOK, EUR/NOK, USD/EUR, NOK/SEK).',
 'publication_nbu': 'НБУ: не позднее 15:30 по времени Киева в день установления (NOK/UAH). Курс действует со следующего рабочего дня.',
 'publication_refresh': 'После публикации нажмите «Обновить курсы», чтобы загрузить новые значения. Успешные проверки общие на 5 минут.',
 'download': 'Скачать CSV',
 'date': 'Дата',
 'table_alt': 'Курсы пяти валютных пар за последние десять рабочих дней; прочерк означает отсутствие значения',
 'missing_note': '— В сохранённой истории нет значения за эту дату. Нажмите «Обновить курсы», чтобы '
                 'проверить публикацию.',
 'download_all': 'Вся сохранённая история в CSV',
 'sources': 'Источники и расчёты',
 'source_nb': 'Источник — [официальный API Norges '
              'Bank](https://www.norges-bank.no/en/topics/Statistics/exchange_rates/). USD/EUR = USD/NOK ÷ '
              'EUR/NOK по одной дате. NOK/SEK — SEK за 1 NOK; котировка за 100 SEK нормализуется перед '
              'обращением. Изменения считаются к предыдущему опубликованному значению. Отсутствующие курсы '
              'выходных и праздников не подставляются.',
 'source_nbu': 'NOK/UAH — [официальный курс НБУ](https://bank.gov.ua/ua/markets/exchangerates), гривен за 1 '
               'NOK. Дата действия курса НБУ может отличаться от даты публикации Norges Bank. Между '
               'значениями разных источников кросс-курс не рассчитывается.',
 'saved_note': 'При первом запуске история загружается автоматически. После успешного обновления '
               'проверка курсов общая для всех посетителей в течение 5 минут. После ошибки повторите '
               'попытку через 30 секунд.',
 'project_folder': 'Папка приложения: {path}',
 'footer': 'Fjord FX · 5 пар · Norges Bank + НБУ · Europe/Oslo',
 'period_change': 'Изменение за период',
 'percent_axis': 'Изменение от начала периода, %',
 'show_mini': 'Показать мини-графики',
 'chart_help': 'Как читать графики',
 'table_scroll': 'Прокрутите таблицу по горизонтали, чтобы увидеть все пары. Дата остаётся видимой.',
 'amount_help': 'При вводе суммы используйте десятичную точку. Нажмите Enter или выйдите из поля, чтобы применить сумму.'}
assert TEXT.keys() == RUSSIAN.keys()
TEXT = {key: (*values, RUSSIAN[key]) for key, values in TEXT.items()}

# PNG images carry intrinsic dimensions, unlike the previous viewBox-only SVGs.
# Keep them embedded so flags render offline and do not depend on emoji fonts.
_FLAG_PNG = {'en': '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',
 'nb': 'iVBORw0KGgoAAAANSUhEUgAAAFgAAABACAIAAAARcieVAAAAr0lEQVR42u3asQ3CMBAFUBulDDuQCWCJTBHGYwpYgg0yBANcuogihZGuMNL71RWWi6ezJctXn+O1ZGT+vPe6TvfDNbE+9vp1vpWecioCAgQIECBAgAABAgQIECBAgAABAgQIECBAdJ4aEfmbNvxr6AgQIP7jjiiXhYKOAAECBAgQILw1dAQIENkZsuYdv+csW2LO0tEAAQIECBAgQIAAAQIECBAgQAgIECBAgADxYzbczhfhvHDOEgAAAABJRU5ErkJggg==',
 'ru': 'iVBORw0KGgoAAAANSUhEUgAAAHgAAABQCAIAAABd+SbeAAAAkklEQVR42u3SQREAIAzAsA0hGEABhnGEnqFiHy6VkGtWVai/gQA0aIEGDVqgQQs0aNACDVqgQYMWaNACDRq0QIMWaNCg1V7GPhQcDVqgQYMWaNACDRq0QIMWaNCgBRq0QIMGLdCgBRo0aPWWd00KjgYt0KBBCzRogQYNWqBBCzRo0AINWqBBgxZo0AINGrRAf9EDFKoFmC41/AIAAAAASUVORK5CYII='}
_FLAG_LABELS = {
    code: f'![{LANGUAGES[code]}](data:image/png;base64,{png} "{LANGUAGES[code]}")'
    for code, png in _FLAG_PNG.items()
}

def flag_label(language):
    return _FLAG_LABELS[language]


_CITY_FLAG_PNG = {
    "oslo": _FLAG_PNG["nb"],
    "kyiv": "iVBORw0KGgoAAAANSUhEUgAAAFgAAABACAIAAAARcieVAAAAaElEQVR42u3QAQ0AAAQAMC1FFUUcpoZ9e4JHZHEUiBAhQoQIESJEiBAhQoQIESJEiBAhQoQIESJEiBAhQoQIEW9NcxSIECFChAgRIkSIECFChAgRIkSIECFChAgRIkSIECFChAgRbyMWvZjN0sjDRBoAAAAASUVORK5CYII=",
}


def city_flag(city):
    return base64.b64decode(_CITY_FLAG_PNG[city])


def tr(language, key, **values):
    return TEXT[key][{"en": 0, "nb": 1, "ru": 2}[language]].format(**values)

def number(value, spec=".4f", *, language="en"):
    text = format(Decimal(str(value)), spec)
    return text if language == "en" else text.replace(",", " ").replace(".", ",")

def pair_label(pair, language):
    base, quote = pair.split("/")
    return tr(language, "unit", base=base, quote=quote)

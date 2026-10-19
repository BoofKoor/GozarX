"""The console's icon language: Telegram premium (custom) emoji.

Every emoji a screen writes keeps its meaning. When the bot's OWNER has Telegram Premium, Telegram
lets the bot draw it as a custom emoji instead (Bot API 9.4: messages the bot sends to private,
group and supergroup chats; channels need a Fragment username). The Unicode emoji is the alternative
text: notifications, screen readers and non-premium views show it, so without Premium the bot looks
exactly as before.

Where each kind comes from (the packs tunnelbot's owner picked; ids carried over from tunnelbot
2026.10.17.6, which checked every one against Telegram and the packs' pictures):
- objects in text (server, node, user, key, …): "SF Symbols" (t.me/addemoji/sfsymbols) —
  monochrome and adaptive (they take the text colour: white in a dark theme, black in a light one).
- actions and arrows (⬆️ ⬇️ ⬅️ ↩️ 🔄 🔀 🔁 ▶️ ⏸ ⏹ ⏭ ◀️ ➡️ 🔢 ♻️): "Twemoji Symbols #1"
  (t.me/addemoji/TwemojiSymbols1) — coloured, still. ➕ stays SF: the Twemoji plus is dark grey and
  disappears in a dark theme.
- buttons: on a plain (uncoloured) button the icon is coloured — the Twemoji object of the same
  emoji (COLOR: Twemoji Objects #1/#2, Travel, Activities, Time & Weather, Hands, Symbols; all by
  @HiEmoji like the flags); on a green / red / blue button it is the adaptive SF one (painted white
  there; a coloured icon would melt into the colour): MONO holds the SF icon of every emoji whose
  text icon is coloured.
- country flags: "Twemoji Flags" #1/#2 (t.me/addemoji/TwemojiFlags1, TwemojiFlags2) — every
  country but Syria (the pack has the flag Syria used before 2025). These are what a location's flag
  becomes in the user's picker and in the delivered config (``ui.flags``).
- the loader of a step that is running (⏳): the blue spinner of
  t.me/addemoji/emoji_fan40_by_TgEmodziBot; 🎉 stays. Only these two move: a column of results reads at a glance when nothing else does.
- logos chosen by the name after a mark (NAMED): "🐧 Ubuntu 24.04" → "Browser & OS"
  (t.me/addemoji/BrowserOS); "📺 YouTube", "🎧 Spotify" → "Social Emojis"; "🧠 Gemini" … → the AI
  logos. The mark alone never becomes a logo.
Status emoji stay plain on purpose (✅ ❌ ⚠️ ⛔️ ℹ️ ⭐️ ☑️ ⬜️ 🆕 🐳 🟢 🔴): already coloured, and still.

The worker asks Telegram about every id once a day (``getCustomEmojiStickers``, see
``services/look``); one Telegram no longer knows is drawn as the plain emoji.
"""

from __future__ import annotations

VS16 = "\ufe0f"


def norm(emoji: str) -> str:
    """'⬅️' and '⬅' are the same emoji (variation selector 16 only asks for the colour form)."""
    return emoji.replace(VS16, "")


# emoji -> custom emoji id, in text (and on buttons when COLOR / MONO don't say otherwise); pack and name in the comment
TEXT: dict[str, str] = {
    norm(k): v
    for k, v in {
        "🏠": "6023896773162967617",  # Дом — menu
        "⬅️": "6321200134583486533",  # TwemojiSymbols1 #32 — back
        "↩️": "6323298127323334001",  # TwemojiSymbols1 #36 — no / revert
        "🧹": "5807679830195444280",  # (same) — undo what the bot changed
        "➕": "5807642902066634351",  # Плюс — new / add
        "🗑": "6021413766669801212",  # Корзина — delete
        "✏️": "6026080811277621020",  # Редактировать в квадрате — rename
        "🔄": "6323348786462590564",  # TwemojiSymbols1 #41 — refresh
        "🔁": "6323059133868148679",  # TwemojiSymbols1 #73 — again / change type / the other panel
        "⬆️": "6323371884796708154",  # TwemojiSymbols1 #26 — update / make first / move up
        "⬇️": "6323432233382184795",  # TwemojiSymbols1 #30 — move down
        "🔑": "6019290828759898301",  # Ключ — key, password
        "🔐": "6019568309417023812",  # Замок — secure login
        "🔒": "6019568309417023812",  # Замок — password logins off
        "🔓": "6019251723082668416",  # Открытый замок — password logins on
        "🔏": "6019161984035986674",  # Touch ID — host key fingerprint
        "🔀": "6323080179207899001",  # TwemojiSymbols1 #72 — Iran ports (routes)
        "🛟": "6019258242843023335",  # Пустой щит — backup (failover)
        "⚖️": "5807788935249665654",  # Разветвление вверх — balance
        "🗄": "6021728265650051545",  # Сервер — servers
        "🖥": "6019608871088167009",  # Монитор — node
        "💻": "6021607757457660145",  # Терминал — operating system
        "🗂": "6026248173268243634",  # Спидометр — panel (dashboard)
        "🌍": "6021443182900812386",  # Глобус — Европа и Африка — the foreign server
        "🌐": "5807928135139728476",  # Глобус — address, network
        "🚇": "6024030612933844303",  # Метро в тоннеле — tunnel
        "🛠": "6021401276904905698",  # Отвёртка и ключ — manage, server prep
        "📄": "6021741567163767583",  # Документ — log, key file
        "📦": "6024106569430472546",  # Коробка с лентой — config profile
        "🔌": "6019346268197759615",  # Электрическая вилка — port, connection test
        "📌": "6021514878789883831",  # Канцелярская кнопка — important note
        "➖": "5807405618008433289",  # Минус — none / remove a target
        "⏭": "6323520769838024799",  # TwemojiSymbols1 #77 — skip one
        "📋": "6026092845775985022",  # Маркированный список — summary
        "💾": "6024111667556653374",  # Закладка — saved
        "⏹": "6323191375911192392",  # TwemojiSymbols1 #87 — stop
        "✍️": "6021741116192201252",  # Клавиатура — type it yourself
        "⌨️": "6021741116192201252",  # (same) — commands
        "🧪": "6021696766359902854",  # Две пробирки — appearance self-test
        "⚙️": "6021582331251268218",  # Шестерёнка — settings of one item
        "🕓": "6032604359794104706",  # Часы — time
        "🏷": "6021594546138257831",  # Бирка — name
        "🧱": "6019328362479097179",  # Щит с клетками — firewall (ufw)
        "👤": "6024039683904772353",  # Контур пользователя — user
        "🚀": "5807414083388971488",  # Воспроизведение — start / apply
        "♻️": "6323547123757352282",  # TwemojiSymbols1 #115 — done before
        "💡": "6024093882097080691",  # Лампочка — tip
        "👇": "6023566962624306038",  # Указательный палец вниз
        "👆": "6021440232258279270",  # Указательный палец вверх
        "🎨": "6021435456254646075",  # Палитра — appearance
        "👁": "6024008227564296298",  # Глаз — show / hide
        "❓": "5807800879553715710",  # Вопрос в круге — help
        "📑": "6021445064096486884",  # Два документа — copy
        "⏳": "4990108972628313185",  # emoji_fan40 #124: the blue spinner — running (animated)
        "🎉": "6023579259115674297",  # Хлопушка — finished (animated)
        # Part 6 (SF Symbols)
        "🧩": "6024065724291488135",  # Пазл — inbound
        "✨": "6021425109678429764",  # Три искры — new config (the guided flow)
        "☁️": "6021401951214770773",  # Облако — Cloudflare, domains; a proxied record
        "👥": "6021690418398239007",  # Два пользователя — squads (users)
        "🎲": "6021391505854306270",  # Игральные кости — another random name / emoji
        "🗺": "6021698802174400671",  # Карта — which domain reaches which node
        "🏳": "6021591694279973430",  # Флаг — a host's country (flag)
        "🔢": "6323436631428695574",  # TwemojiSymbols1 #150 — a port number
        # Part 8: more of the Twemoji symbols
        "▶️": "6323301979908998512",  # TwemojiSymbols1 #75 — turn on (a host)
        "⏸": "6323377421009552810",  # TwemojiSymbols1 #86 — off (a host)
        "◀️": "6323133642960799652",  # TwemojiSymbols1 #79 — back to a list
        "➡️": "6323426469536073270",  # TwemojiSymbols1 #28 — next / continue
    }.items()
}

# a plain (uncoloured) button: the coloured Twemoji object of the same emoji (all by @HiEmoji, static); not here:
# ➕ ➖ 🔌 (dark grey: they disappear in a dark theme) and 🏳 (no Twemoji white flag in these packs)
COLOR: dict[str, str] = {
    norm(k): v
    for k, v in {
        "🏠": "6323335137056523755",  # TwemojiTravel #25
        "✏️": "6323341536557794883",  # TwemojiObjects1 #148
        "🗂": "6323470875202946396",  # TwemojiObjects1 #158
        "🔑": "6323403268122740629",  # TwemojiObjects1 #182
        "🌍": "6320805714851792566",  # TwemojiTravel #0
        "🌐": "6323144028191721118",  # TwemojiTravel #3
        "🛠": "6323218545874306931",  # TwemojiObjects1 #188
        "🎨": "6323611883274241646",  # TwemojiActivities #81
        "🚇": "6323309487511832342",  # TwemojiTravel #71
        "🖥": "6323347588166714949",  # TwemojiObjects1 #82
        "💻": "6323281883757020916",  # TwemojiObjects1 #81
        "🧩": "6323269299502843936",  # TwemojiActivities #66
        "⚙️": "6323340041909175948",  # TwemojiObjects1 #199
        "🏷": "6323468994007271113",  # TwemojiObjects1 #124
        "✨": "6323365755878378381",  # TwemojiActivities #5
        "🧪": "6323595880226096589",  # TwemojiObjects2 #10
        "📄": "6323234179555263965",  # TwemojiObjects1 #119
        "📑": "6323281660418722019",  # TwemojiObjects1 #122
        "📋": "6323602795123443087",  # TwemojiObjects1 #167
        "📌": "6323444654427604698",  # TwemojiObjects1 #168
        "📦": "6323328338123293863",  # TwemojiObjects1 #141
        "💾": "6323412875964581094",  # TwemojiObjects1 #88
        "🗄": "6321207771035338339",  # TwemojiObjects1 #176
        "🗑": "6323174196042008130",  # TwemojiObjects1 #177
        "🔒": "6323546342073304496",  # TwemojiObjects1 #178
        "🔓": "6321004468758382236",  # TwemojiObjects1 #179
        "🔏": "6321094534222579088",  # TwemojiObjects1 #180
        "🔐": "6323104939694360272",  # TwemojiObjects1 #181
        "💡": "6323337542238209506",  # TwemojiObjects1 #104
        "⌨️": "6323559471788328991",  # TwemojiObjects1 #84
        "⚖️": "6323064661491058614",  # TwemojiObjects2 #1
        "🧹": "6323548936233551598",  # TwemojiObjects2 #38
        "🎲": "6323055066534119059",  # TwemojiActivities #65
        "☁️": "6323279006128932933",  # TwemojiTimeWeather #52
        "🕓": "6323553239790782322",  # TwemojiTimeWeather #15
        "🗺": "6323305098055255968",  # TwemojiTravel #4
        "🛟": "6323511088981739579",  # TwemojiTravel #117
        "🚀": "6323134635098244581",  # TwemojiTravel #136
        "🧱": "6323121943469885418",  # TwemojiTravel #19
        "✍️": "6323293544593229469",  # TwemojiHands #61
        "👁": "6323604856707745766",  # TwemojiHands #62
        "👤": "6323422956252825262",  # TwemojiHands #54
        "👥": "6323318322259560277",  # TwemojiHands #55
        "👇": "6323574950850463186",  # TwemojiHands #20
        "👆": "6323364548992567124",  # TwemojiHands #18
        "❓": "6323309062310069525",  # TwemojiSymbols1 #107
        "✅": "6323524880121726602",  # TwemojiSymbols1 #121
        "❌": "6323186419518932861",  # TwemojiSymbols1 #124
    }.items()
}

# a green / red / blue button: the adaptive SF icon for every emoji whose text icon above is coloured (sfsymbols)
MONO: dict[str, str] = {
    norm(k): v
    for k, v in {
        "⬅️": "5805509901048356965",  # Стрелка влево
        "↩️": "5807679830195444280",  # Отменить действие
        "🔄": "5807492110059838726",  # Две круговые стрелки
        "🔁": "5807767434643382465",  # Повтор двух направлений
        "⬆️": "5807601906603792598",  # Стрелка вверх
        "⬇️": "5807557921843715576",  # Стрелка вниз
        "🔀": "5807880911974308745",  # Перемешать
        "⏭": "5807405618008433289",  # Минус
        "⏹": "5807622114424924272",  # Стоп в круге
        "♻️": "5805232145513322780",  # Три стрелки переработки
        "🔢": "6026201306585110323",  # Знак номера
        "▶️": "5807414083388971488",  # Воспроизведение
        "⏸": "5807945302124012062",  # Пауза
        "◀️": "5807792908094413296",  # Шеврон влево
        "➡️": "5807453545548487345",  # Стрелка вправо
        "⏳": "5945191033607297698",  # Загрузчик из капель (a blue spinner would vanish on a blue button)
    }.items()
}

# only as the icon of a coloured button; in text these stay the coloured status emoji (plain buttons: COLOR)
BUTTON: dict[str, str] = {
    norm(k): v
    for k, v in {
        "✅": "6019175208240289774",  # Проверенная отметка — yes / confirm
        "❌": "5807692706507399432",  # Крестик — cancel
    }.items()
}

# ISO country code -> flag ("Twemoji Flags" #1/#2; Syria left out: the pack has its flag from before 2025)
FLAGS: dict[str, str] = {
    "AC": "6323062758820546386",
    "AD": "6323160447851693561",
    "AE": "6323431000726571083",
    "AF": "6321048457813427859",
    "AG": "6323525124934862379",
    "AI": "6321062223183611280",
    "AL": "6323108908244141708",
    "AM": "6323236391463421376",
    "AO": "6323526533684135466",
    "AQ": "6323220903811352471",
    "AR": "6323412437877917345",
    "AS": "6323461181461759981",
    "AT": "6323259665891198368",
    "AU": "6323341691176617459",
    "AW": "6323197023793186704",
    "AX": "6323151574449260103",
    "AZ": "6323575251498174463",
    "BA": "6323446973709944370",
    "BB": "6323362461638461356",
    "BD": "6323319576390010145",
    "BE": "6320961935697250101",
    "BF": "6323218532989404821",
    "BG": "6321087679454774976",
    "BH": "6323567563506714608",
    "BI": "6323142610852513890",
    "BJ": "6323527001835570714",
    "BL": "6323147562949805344",
    "BM": "6323577368917051174",
    "BN": "6323208607319984098",
    "BO": "6323614528974095845",
    "BQ": "6323547432994998057",
    "BR": "6323066615701177922",
    "BS": "6323310973570516653",
    "BT": "6323161513003582742",
    "BV": "6323085569391855089",
    "BW": "6323569745350100079",
    "BY": "6323582299539506720",
    "BZ": "6323210548645201546",
    "CA": "6323325327351219831",
    "CC": "6323377369469945669",
    "CD": "6323418803019450340",
    "CF": "6323271524295902921",
    "CG": "6323061813927741659",
    "CH": "6323198986593240779",
    "CI": "6323079152710715047",
    "CK": "6320858066208164317",
    "CL": "6323602322677040561",
    "CM": "6321186163054872003",
    "CN": "6323453751168337485",
    "CO": "6323306515394463125",
    "CP": "6320863349017937664",
    "CR": "6323197058152924579",
    "CU": "6321285540008167466",
    "CV": "6323318863425438996",
    "CW": "6320822624138036756",
    "CX": "6323548098714929117",
    "CY": "6323092071972341179",
    "CZ": "6321085042344854835",
    "DE": "6320817337033295141",
    "DG": "6323272748361582136",
    "DJ": "6323489579785521006",
    "DK": "6321081249888732937",
    "DM": "6323555937030243495",
    "DO": "6323239531084514835",
    "DZ": "6320872419988866632",
    "EA": "6323322982299076099",
    "EC": "6323091599525938608",
    "EE": "6323415560319141848",
    "EG": "6323516260122363644",
    "EH": "6323233376396379737",
    "ER": "6323303663536178598",
    "ES": "6323315062379382237",
    "ET": "6323513966609827733",
    "EU": "6323217102765295143",
    "FI": "6323216772052813661",
    "FJ": "6323084272311731891",
    "FK": "6323262698138109211",
    "FM": "6323238002076157177",
    "FO": "6323375106022180362",
    "FR": "6323570711717742330",
    "GA": "6323504904228833317",
    "GB": "6323589145717376403",
    "GD": "6323292518096045680",
    "GE": "6323445178413614682",
    "GF": "6323434522599753301",
    "GG": "6320948900471506677",
    "GH": "6323117287725336347",
    "GI": "6323183937027835571",
    "GL": "6323165228150294044",
    "GM": "6323492895500273079",
    "GN": "6323076562845435163",
    "GP": "6323582479928133192",
    "GQ": "6323525026150614363",
    "GR": "6321231462074943127",
    "GS": "6323176287691081361",
    "GT": "6323603130130892243",
    "GU": "6321143037288253009",
    "GW": "6323578477018613462",
    "GY": "6323213263064532512",
    "HK": "6323198630110954654",
    "HM": "6323492496068314710",
    "HN": "6321362145044858471",
    "HR": "6323319494785632248",
    "HT": "6323244977103046600",
    "HU": "6321025453968590579",
    "IC": "6323390310206408235",
    "ID": "6323400927365564310",
    "IE": "6323543692078482922",
    "IL": "6323257307954153312",
    "IM": "6323371631393638205",
    "IN": "6323181871148566277",
    "IO": "6321209463252453235",
    "IQ": "6323555846835930376",
    "IR": "6323450190640449363",
    "IS": "6323117425164289952",
    "IT": "6323471399188957082",
    "JE": "6323090500014310987",
    "JM": "6323139007374952483",
    "JO": "6323327281561339424",
    "JP": "6323356796576597627",
    "KE": "6323438718782801772",
    "KG": "6323615997852910673",
    "KH": "6323476901042063012",
    "KI": "6323481986283341414",
    "KM": "6323438972185872646",
    "KN": "6321305472951389117",
    "KP": "6323114272658294438",
    "KR": "6323152716910561397",
    "KW": "6323445556370736451",
    "KY": "6320862107772389525",
    "KZ": "6323135275048371614",
    "LA": "6321044132781361052",
    "LB": "6323067444629866313",
    "LC": "6323294437946426779",
    "LI": "6323465493608925227",
    "LK": "6323214873677268876",
    "LR": "6323077413248959789",
    "LS": "6323234312699250177",
    "LT": "6323054585497781832",
    "LU": "6321029697396278883",
    "LV": "6323270540748392568",
    "LY": "6323500948563953161",
    "MA": "6320872424283833926",
    "MC": "6323485486681687477",
    "MD": "6323242408712602989",
    "ME": "6323534672647161483",
    "MF": "6323364609122108931",
    "MG": "6323560902012438469",
    "MH": "6323227870248306588",
    "MK": "6323232203870307896",
    "ML": "6323166941842245258",
    "MM": "6323266194241488281",
    "MN": "6323272134181258987",
    "MO": "6323557758096377611",
    "MP": "6323072886353431893",
    "MQ": "6323396348930426714",
    "MR": "6323584657476552790",
    "MS": "6323164283257489048",
    "MT": "6321169996797970574",
    "MU": "6323203852791186881",
    "MV": "6323219834364495248",
    "MW": "6323128819712525696",
    "MX": "6323336670359848647",
    "MY": "6323541952616728054",
    "MZ": "6323073015202449636",
    "NA": "6323318537007924754",
    "NC": "6323125319314179901",
    "NE": "6323613648505800777",
    "NF": "6323419567523628257",
    "NG": "6323153803537287161",
    "NI": "6323200554256303845",
    "NL": "6323198024520566067",
    "NO": "6323393084755281353",
    "NP": "6323350079247746873",
    "NR": "6323496000761628105",
    "NU": "6323546526756899374",
    "NZ": "6323152712615593815",
    "OM": "6323117794531477774",
    "PA": "6323103466520577575",
    "PE": "6323507605763262082",
    "PF": "6323558917737547607",
    "PG": "6323612553289139650",
    "PH": "6323190362298910475",
    "PK": "6323535974022252140",
    "PL": "6323602387101550101",
    "PM": "6320895724481415215",
    "PN": "6321291462768068425",
    "PR": "6323457200027076155",
    "PS": "6323257144745395640",
    "PT": "6323261461187528569",
    "PW": "6323271584425444734",
    "PY": "6323157626058180394",
    "QA": "6323069433199723875",
    "RE": "6323079745416202005",
    "RO": "6323204514216150852",
    "RS": "6323476999826310994",
    "RU": "6323139226418284334",
    "RW": "6323209539327886855",
    "SA": "6323493926292424101",
    "SB": "6323197496239588762",
    "SC": "6321207715200763481",
    "SD": "6323465695472388250",
    "SE": "6320922812840150877",
    "SG": "6323223764259570834",
    "SH": "6323458552941774129",
    "SI": "6323396567973758479",
    "SK": "6323308396590139202",
    "SL": "6323487479546512920",
    "SM": "6323376317202957753",
    "SN": "6320811418568361413",
    "SO": "6323463621003183505",
    "SR": "6323299484532999421",
    "SS": "6321019913460779018",
    "ST": "6320979540768196479",
    "SV": "6323151583039194562",
    "SX": "6323585499290142513",
    "SZ": "6321242508730828949",
    "TA": "6323171241104508516",
    "TC": "6323068728825087940",
    "TD": "6323390224307062186",
    "TF": "6323541720688494392",
    "TG": "6323591757057492818",
    "TH": "6323081815590438980",
    "TJ": "6323529454261896950",
    "TK": "6320884540386576371",
    "TL": "6323296525300532878",
    "TM": "6323414482282350254",
    "TN": "6323420903258457844",
    "TO": "6323459330330855189",
    "TR": "6321003171678259486",
    "TT": "6323273787743668306",
    "TV": "6321269455355643417",
    "TW": "6323183215473330063",
    "TZ": "6323331675312883515",
    "UA": "6323289850921354919",
    "UG": "6323467039797150870",
    "UM": "6321193412959668105",
    "UN": "6323494299954578906",
    "US": "6323374027985389586",
    "UY": "6323182231925819139",
    "UZ": "6323430017179059570",
    "VA": "6321134039331767912",
    "VC": "6323388948701775579",
    "VE": "6323244040800175517",
    "VG": "6321258954160604865",
    "VI": "6323433191159891530",
    "VN": "6323320044541445734",
    "VU": "6323271184993486642",
    "WF": "6323428208997828313",
    "WS": "6323227281837786699",
    "XK": "6323442472584217958",
    "YE": "6323263256483858365",
    "YT": "6323450452633456781",
    "ZA": "6323176502439445834",
    "ZM": "6323614928406054835",
    "ZW": "6323177576181270239",
}

# a mark followed by a name -> that name's logo ("🐧 Ubuntu 24.04" → Ubuntu's); the mark alone stays plain
NAMED: dict[str, tuple[tuple[tuple[str, ...], str], ...]] = {
    norm(k): v
    for k, v in {
        "🐧": (
            (("ubuntu",), "6327791711086970160"),  # BrowserOS #18
            (("debian",), "6325500406164096402"),  # #19
            (("linux mint", "linuxmint"), "6325732789664614236"),  # #20
            (("arch",), "6327913645208503606"),  # #21
            (("centos",), "6325777465914426810"),  # #22
            (("fedora",), "6325601608478492444"),  # #23
            (("kali",), "6325338490192004905"),  # #24
            (("pop!_os", "pop_os", "pop!os"), "6325666204786623880"),  # #25
            (("red hat", "rhel"), "6327790164898743674"),  # #26
            (("opensuse", "suse", "sles"), "6327896010072786325"),  # #27
            (("manjaro",), "6328118506558588690"),  # #28
            (("",), "6328099527098107065"),
        ),  # #17 Tux: any other Linux
        "📺": ((("youtube",), "6319028560463922831"),),  # SocialEmojis: YouTube
        "🎧": ((("spotify",), "6319076999105087378"),),  # SocialEmojis: Spotify
        "🧠": (
            (("gemini",), "5944955909917646080"),  # catalog «Нейросети»: Gemini
            (("chatgpt",), "5945217417591397712"),  # ChatGPT
            (("claude",), "5945210167686601730"),  # Claude
            (("grok",), "5944959539165012786"),  # Grok
            (("perplexity",), "5945200220542344867"),
        ),  # Perplexity
    }.items()
}

ANIMATED = {norm("⏳"), norm("🎉")}


def named_icon(emoji: str, after: str) -> str | None:
    """The logo for a mark followed by a name ("🐧", " Ubuntu 24.04"), or None."""
    opts = NAMED.get(norm(emoji))
    if not opts:
        return None
    a = after.lstrip().lower()
    for names, eid in opts:
        if any(a.startswith(n) for n in names):
            return eid
    return None


def button_id(emoji: str, coloured_button: bool) -> str | None:
    """The icon of a button that starts with this emoji: a plain button gets the coloured one, a green / red / blue
    button the adaptive one (white on the colour)."""
    e = norm(emoji)
    if coloured_button:
        return MONO.get(e) or TEXT.get(e) or BUTTON.get(e)
    return COLOR.get(e) or TEXT.get(e) or BUTTON.get(e)


def flag_code(emoji: str) -> str | None:
    """'🇩🇪' -> 'DE' (two regional indicator symbols), else None."""
    if len(emoji) != 2 or not all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in emoji):
        return None
    return "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in emoji)


def all_ids() -> set[str]:
    return (
        set(TEXT.values())
        | set(BUTTON.values())
        | set(COLOR.values())
        | set(MONO.values())
        | set(FLAGS.values())
        | {e for v in NAMED.values() for _, e in v}
    )

#!/usr/bin/env python3
# main.py
# Telegram Store Bot (pyTelegramBotAPI)
# Implementa funcionalidades pedidas: menu dinâmico de níveis, usuários, cargos, financeiro,
# adição de cartões, entrega formatada, checker (simulado ou via API), logs, spamon, etc.

import csv
import os
import json
import threading
import time
import random
import datetime
import traceback
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

# pyTelegramBotAPI
try:
    import telebot
    from telebot import types
except Exception as e:
    print("pyTelegramBotAPI (telebot) is required to run this bot. Install with: pip install pyTelegramBotAPI")
    raise

# ----------------------------
# Configuration
# ----------------------------
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'REPLACE_WITH_YOUR_TOKEN')
CHECKER_API_URL = os.getenv('CHECKER_API_URL')
REFS_CHANNEL = os.getenv('REFS_CHANNEL', '@haxorstorerefs')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@haxorsuporte')
DATA_DIR = os.getenv('DATA_DIR', 'data')
USERS_FILE = os.path.join(DATA_DIR, 'usuarios.json')
CARDS_FILE = os.path.join(DATA_DIR, 'cartoes.json')
MOD_STATS_FILE = os.path.join(DATA_DIR, 'mod_stats.json')
LOG_FILE = os.path.join(DATA_DIR, 'logs.txt')
USUARIOS_CSV = os.path.join(DATA_DIR, 'usuarios.csv')
LEADS_CSV = os.path.join(DATA_DIR, 'leads.csv')
MEMBERS_LIST_CSV = os.path.join(DATA_DIR, 'membros1.csv')

BIN_LEVELS = {
    "4": ("VISA", "CLASSIC"),
    "42": ("VISA", "PLATINUM"),
    "44": ("VISA", "PLATINUM"),
    "45": ("VISA", "GOLD"),
    "46": ("VISA", "SIGNATURE"),
    "48": ("VISA", "INFINITE"),
    "51": ("MASTERCARD", "STANDARD"),
    "54": ("MASTERCARD", "GOLD"),
    "55": ("MASTERCARD", "WORLD"),
    "22": ("MASTERCARD", "WORLD"),
    "34": ("AMEX", "PLATINUM"),
    "37": ("AMEX", "PLATINUM"),
}
PREMIUM_LEVELS = {"PLATINUM", "GOLD", "SIGNATURE", "INFINITE", "WORLD", "BLACK"}

os.makedirs(DATA_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# ----------------------------
# Utility: JSON persistence
# ----------------------------

def now_str():
    return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def load_json(path: str, default: Any):
    if not os.path.exists(path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        try:
            os.rename(path, path + '.bak')
        except Exception:
            pass
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default


def save_json(path: str, data: Any):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def log_admin(action_line: str):
    entry = f'[{now_str()}] {action_line}\n'
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception as e:
        print('Failed to write log:', e)


users = load_json(USERS_FILE, {})
cards = load_json(CARDS_FILE, [])
mod_stats = load_json(MOD_STATS_FILE, {})


def ensure_user(uid: str, username: Optional[str], name: Optional[str]):
    if uid not in users:
        users[uid] = {
            'id': uid,
            'name': name or '',
            'username': username or '',
            'role': 'user',
            'balance': 0.0,
            'points': 0,
            'created_at': now_str(),
            'bought_cards': 0,
            'mix_count': 0,
            'pix_recharges': 0,
            'manuals': 0
        }
        save_json(USERS_FILE, users)


def is_admin(uid: str) -> bool:
    return users.get(uid, {}).get('role') == 'admin'


def is_mod(uid: str) -> bool:
    return users.get(uid, {}).get('role') in ('mod', 'admin')


def count_by_level() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in cards:
        level = c.get('NIVEL', 'UNKNOWN')
        counts[level] = counts.get(level, 0) + 1
    return counts


def find_card_for_level(level: str) -> Optional[Dict[str, Any]]:
    for c in cards:
        if c.get('NIVEL', '').upper() == level.upper():
            return c
    return None


def pop_card(card: Dict[str, Any]) -> None:
    try:
        cards.remove(card)
        save_json(CARDS_FILE, cards)
    except Exception as e:
        print('Error removing card:', e)


def check_card_online(card: Dict[str, Any]) -> bool:
    try:
        if CHECKER_API_URL:
            payload = json.dumps(card).encode('utf-8')
            req = urllib.request.Request(CHECKER_API_URL, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return str(data.get('status', '')).lower() == 'live'
        return random.random() < 0.8
    except Exception as e:
        print('Checker error:', e)
        return False


def format_delivery(card: Dict[str, Any]) -> str:
    numero = card.get('NUMERO', 'N/A')
    mes = card.get('MES', 'N/A')
    ano = card.get('ANO', 'N/A')
    cvv = card.get('CVV', 'N/A')
    banco = card.get('BANCO', 'NIVEL')
    nivel = card.get('NIVEL', 'N/A')
    nome = card.get('NOME', 'N/A')
    cpf = card.get('CPF', 'N/A')
    nasc = card.get('NASC', 'N/A')
    estado = card.get('ESTADO', 'N/A')
    cidade = card.get('CIDADE', 'N/A')
    tel = card.get('TEL', 'N/A')
    email = card.get('EMAIL', 'N/A')

    parts = nome.split()
    if len(parts) >= 2:
        first = parts[0]
        initials = ' '.join([p[0] + '.' for p in parts[1:]])
        titular = f"{first} {initials}"
    else:
        titular = nome

    return (
        f"Compra efetuada! Número: {numero} Validade: {mes}/{ano} CVV: {cvv} Bandeira: {banco} Nivel: {nivel}\n\n"
        f"👤 Titular: {titular}\n"
        f"Nome completo: {nome} CPF: {cpf} Data de nascimento: {nasc}\n"
        f"Estado de origem: {estado} Cidade de origem: {cidade}\n\n"
        f"Telefone: {tel} E-mail: {email}"
    )


def lookup_bin_info(card_number: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = ''.join(ch for ch in str(card_number or '') if ch.isdigit())
    prefix2 = cleaned[:2]
    prefix6 = cleaned[:6]

    static_brand, static_level = BIN_LEVELS.get(prefix2, BIN_LEVELS.get(prefix6[:2], ("UNKNOWN", "CLASSIC")))

    try:
        if prefix6:
            url = f'https://lookup.binlist.net/{prefix6}'
            req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8', 'ignore'))
            if isinstance(data, dict):
                brand = str(data.get('scheme') or data.get('brand') or static_brand or fallback.get('BANCO') or 'N/A').title()
                bank_name = data.get('bank', {})
                bank = str(bank_name.get('name') if isinstance(bank_name, dict) else bank_name or fallback.get('BANCO') or 'N/A')
                country_data = data.get('country', {})
                country = str(country_data.get('name') if isinstance(country_data, dict) else country_data or fallback.get('PAIS') or 'N/A')
                level = str(data.get('level') or static_level or fallback.get('NIVEL') or 'CLASSIC').upper()
                ctype = str(data.get('type') or 'credit').lower()
                return {
                    'brand': brand,
                    'bank': bank,
                    'level': level,
                    'country': country,
                    'type': ctype
                }
    except Exception:
        pass

    return {
        'brand': str(static_brand or fallback.get('BANCO') or 'N/A'),
        'bank': str(fallback.get('BANCO') or 'N/A'),
        'level': str(static_level or fallback.get('NIVEL') or 'CLASSIC').upper(),
        'country': str(fallback.get('PAIS') or 'N/A'),
        'type': 'credit'
    }


def fetch_bin_info(bin_number: str) -> Dict[str, Any]:
    cleaned = ''.join(ch for ch in str(bin_number or '') if ch.isdigit())
    prefix6 = cleaned[:6]
    if len(prefix6) < 6:
        return {'brand': 'N/A', 'bank': 'N/A', 'level': 'CLASSIC', 'country': 'N/A', 'type': 'credit'}

    try:
        url = f'https://lookup.binlist.net/{prefix6}'
        req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8', 'ignore'))
        if not isinstance(data, dict):
            raise ValueError('BIN API returned non-object')

        brand = str(data.get('scheme') or data.get('brand') or 'N/A').title()
        bank_name = data.get('bank', {})
        bank = str(bank_name.get('name') if isinstance(bank_name, dict) else bank_name or 'N/A')
        country_data = data.get('country', {})
        country = str(country_data.get('name') if isinstance(country_data, dict) else country_data or 'N/A')
        level = str(data.get('level') or 'CLASSIC').upper()
        return {
            'brand': brand,
            'bank': bank,
            'level': level,
            'country': country,
            'type': str(data.get('type') or 'credit').lower(),
        }
    except Exception:
        return lookup_bin_info(prefix6, {})


def build_purchase_receipt(card: Dict[str, Any], user: Dict[str, Any], level: str, price: float, auth_ref: str) -> str:
    bin_info = lookup_bin_info(card.get('NUMERO'), card)
    numero = str(card.get('NUMERO', 'N/A')).strip()
    mes = str(card.get('MES', 'N/A')).strip()
    ano = str(card.get('ANO', 'N/A')).strip()
    cvv = str(card.get('CVV', 'N/A')).strip()
    cpf = str(card.get('CPF', 'N/A')).strip()
    nome = str(card.get('NOME', 'N/A')).strip()

    parts = nome.split()
    if len(parts) >= 2:
        initials = ''.join(p[0].upper() + '.' for p in parts[1:])
        nome_abrev = f"{parts[0]} {initials}".strip()
    else:
        nome_abrev = nome

    brand = str(bin_info.get('brand') or card.get('BANCO') or 'N/A')
    bank = str(bin_info.get('bank') or card.get('BANCO') or 'N/A')
    level_name = str(bin_info.get('level') or card.get('NIVEL') or level or 'CLASSIC').upper()
    country = str(bin_info.get('country') or card.get('PAIS') or 'N/A')
    current_balance = float(user.get('balance', 0.0) or 0.0)

    return (
        "✨ Compra realizada!\n\n"
        f"💳 Cartão: {numero}\n"
        f"📅 Validade: {mes}/{ano}\n"
        f"🔐 CVV: {cvv}\n\n"
        f"💳 Bandeira: {brand}\n"
        f"💠 Nível: {level_name}\n"
        "⚜️ Tipo: CREDIT\n"
        f"🏦 Banco: {bank}\n"
        f"🌍 País: {country}\n\n"
        "Dados do Titular:\n\n"
        f"👤 Nome: {nome_abrev}\n"
        f"🪪 CPF: {cpf}\n\n"
        f"🔍 Retorno do Checker: Transação autorizada (rdAuthGater LIVE) ({auth_ref})\n"
        f"💸 Valor: R$ {float(price):.2f}\n"
        f"💰 Seu saldo atual: R$ {current_balance:.2f}"
    )


def load_csv_rows(csv_path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    try:
        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row is None:
                    continue
                cleaned = {str(k).strip(): (str(v).strip() if v is not None else '') for k, v in row.items()}
                if any((v or '').strip() for v in cleaned.values()):
                    rows.append(cleaned)
    except Exception as exc:
        print(f'CSV import failed for {csv_path}: {exc}')
    return rows


def build_purchase_notification_message(card_data: Dict[str, Any], buyer_id: str, price: float, level: str, event_dt: Optional[str] = None) -> str:
    cleaned = ''.join(ch for ch in str(card_data.get('NUMERO') or card_data.get('card') or '') if ch.isdigit())
    bin_prefix = cleaned[:6] if len(cleaned) >= 6 else ''.join(str(random.randint(0, 9)) for _ in range(6))
    card_number = ''.join(ch for ch in str(card_data.get('NUMERO') or f"BIN{bin_prefix}{''.join(str(random.randint(0, 9)) for _ in range(6))}") if ch.isdigit() or ch.isalpha())
    if not card_number:
        card_number = f"BIN{bin_prefix}{''.join(str(random.randint(0, 9)) for _ in range(5))}"
    bin_info = fetch_bin_info(bin_prefix)
    level_name = str(level or card_data.get('NIVEL') or bin_info.get('level') or 'CLASSIC').upper()
    bank = str(bin_info.get('bank') or card_data.get('BANCO') or 'N/A')
    country = str(bin_info.get('country') or card_data.get('PAIS') or 'N/A')
    brand = str(bin_info.get('brand') or card_data.get('BANCO') or 'N/A')
    dt = event_dt or datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')
    value = float(price or card_data.get('VALOR') or 0.0)
    return (
        "💎 | Cartão comprado com sucesso!\n\n"
        f"💳 Cartão: {card_number}\n"
        f"⏰ Data/Hora: {dt}\n"
        f"🏅 Nível: {level_name}\n"
        f"🔓 BIN: {bin_prefix}\n"
        f"🏦 Banco: {bank}\n"
        f"🌏 País: {country}\n"
        f"🏴󠁧󠁢󠁥󠁮󠁧󠁿 Bandeira: {brand}\n"
        f"🆔: {buyer_id}\n"
        f"💲 Valor: R$ {value:.2f}\n\n"
        "🚀 => @CYBERHAXORSTORE_BOT"
    )


def build_fake_purchase_message(csv_row: Optional[Dict[str, str]] = None) -> str:
    record = csv_row or {}
    buyer_id = str(record.get('User ID') or record.get('id') or random.randint(100000, 999999))
    level = str(record.get('level') or record.get('NIVEL') or record.get('Level') or 'GOLD').upper()
    value = 49.90
    value_raw = str(record.get('value') or record.get('VALOR') or record.get('Value') or '49.90')
    try:
        value = float(value_raw.replace(',', '.'))
    except Exception:
        value = 49.90
    dt = str(record.get('date') or record.get('Date') or datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S'))

    bin_prefix = str(record.get('bin') or record.get('BIN') or random.choice(['455673', '518328', '411111', '536524', '601160', '542523', '374101', '409961']))
    brand_data = fetch_bin_info(bin_prefix)
    card_number = f"BIN{bin_prefix}{''.join(str(random.randint(0, 9)) for _ in range(6))}"
    return (
        "💎 | Cartão comprado com sucesso!\n\n"
        f"💳 Cartão: {card_number}\n"
        f"⏰ Data/Hora: {dt}\n"
        f"🏅 Nível: {level}\n"
        f"🔓 BIN: {bin_prefix}\n"
        f"🏦 Banco: {brand_data.get('bank') or 'N/A'}\n"
        f"🌏 País: {brand_data.get('country') or 'N/A'}\n"
        f"🏴󠁧󠁢󠁥󠁮󠁧󠁿 Bandeira: {brand_data.get('brand') or 'N/A'}\n"
        f"🆔: {buyer_id}\n"
        f"💲 Valor: R$ {value:.2f}\n\n"
        "🚀 => @CYBERHAXORSTORE_BOT"
    )


def welcome_header_text() -> str:
    return (
        "╔══════════════════════════════╗\n"
        "║          HONOR CC          ║\n"
        "╚══════════════════════════════╝\n\n"
        "✨ Bem-vindo à Honor CC!\n"
        "Aqui você compra CCs de qualidade com saldo pré-pago — rápido e direto.\n\n"
        "Escolha uma opção abaixo:"
    )


def main_menu_markup() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.row('🛒 Loja CC', '💰 Saldo')
    kb.row('💳 Depositar', '📜 Histórico')
    kb.row('🆘 Suporte', '🌐 Language')
    kb.row('⚡ Honor Central — CHK • CC • GG')
    return kb


def levels_inline_markup() -> types.InlineKeyboardMarkup:
    counts = count_by_level()
    ikb = types.InlineKeyboardMarkup()
    buttons = []
    for lvl, cnt in counts.items():
        buttons.append(types.InlineKeyboardButton(text=f"{lvl} | {cnt}", callback_data=f"buy_level::{lvl}"))
    row = []
    for b in buttons:
        row.append(b)
        if len(row) == 2:
            ikb.row(*row)
            row = []
    if row:
        ikb.row(*row)
    ikb.row(types.InlineKeyboardButton('Voltar', callback_data='back::menu'))
    return ikb


@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, welcome_header_text())
    bot.send_message(message.chat.id, '⚡ Menu principal', reply_markup=main_menu_markup())


@bot.message_handler(commands=['menu'])
def cmd_menu(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, '⚡ HONOR CC', reply_markup=main_menu_markup())


@bot.message_handler(func=lambda m: m.text in ['Compre Aqui', 'Loja CC', '🛒 Loja CC'])
def handle_compre(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, '✨ Escolha um nível para continuar sua compra\n\n📦 | Há cartões disponíveis', reply_markup=levels_inline_markup())


@bot.message_handler(func=lambda m: m.text in ['Suas Informações', 'Saldo', '💰 Saldo'])
def handle_info(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    u = users[uid]
    text = (
        f"✨ Suas Informações 👤\n"
        f"Nome: {u.get('name')}\n"
        f"🌐 User: @{u.get('username')}\n"
        f"👑 Admin: {'Sim' if u.get('role') == 'admin' else 'Não'}\n"
        f"🛠 Suporte: {'Sim' if u.get('role') in ('admin', 'mod') else 'Não'}\n"
        f"🚫 Banido: Não\n"
        f"📅 Data de cadastro: {u.get('created_at')}\n"
        f"🆔 ID da carteira: {u.get('id')}\n"
        f"💰 Saldo: R$ {u.get('balance', 0.0):.2f}\n"
        f"⭐ Pontos: {u.get('points', 0)}\n\n"
        f"Cartões comprados: {u.get('bought_cards', 0)}\n"
        f"Mixs: {u.get('mix_count', 0)}\n"
        f"Recargas Pix: {u.get('pix_recharges', 0)}\n"
        f"Manuais: {u.get('manuals', 0)}"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text in ['Depositar', '💳 Depositar'])
def handle_depositar(message):
    bot.send_message(message.chat.id, '💳 Depósito via Pix/Transferência\n\nEnvie o comprovante para o suporte ou use o canal da loja.\n\n📌 Suporte: ' + SUPPORT_USERNAME)


@bot.message_handler(func=lambda m: m.text in ['Histórico', '📜 Histórico'])
def handle_historico(message):
    bot.send_message(message.chat.id, '📜 Seu histórico de compras aparecerá aqui em breve.\n\nUse /menu para voltar ao menu principal.')


@bot.message_handler(func=lambda m: m.text in ['Suporte', '🆘 Suporte'])
def handle_suporte(message):
    bot.send_message(message.chat.id, '🛟 Suporte: ' + SUPPORT_USERNAME + '\n\nSolicite ajuda diretamente no suporte da loja.')


@bot.message_handler(func=lambda m: m.text in ['Language', '🌐 Language'])
def handle_language(message):
    bot.send_message(message.chat.id, '🌐 Idioma atual: Português (Brasil)\n\nUse o menu em PT-BR.')


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: types.CallbackQuery):
    data = call.data or ''
    try:
        if data.startswith('buy_level::'):
            level = data.split('::', 1)[1]
            bot.answer_callback_query(call.id)
            process_purchase_level(call.message, call.from_user, level)
        elif data == 'back::menu':
            bot.edit_message_text('Menu Principal', call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, 'Menu Principal', reply_markup=main_menu_markup())
        else:
            bot.answer_callback_query(call.id, 'Ação desconhecida')
    except Exception:
        traceback.print_exc()
        bot.answer_callback_query(call.id, 'Erro ao processar ação')


def process_purchase_level(message, from_user, level: str):
    uid = str(from_user.id)
    ensure_user(uid, from_user.username, from_user.first_name)
    user = users[uid]

    candidate = None
    for c in cards:
        if c.get('NIVEL', '').upper() == level.upper():
            candidate = c
            break
    if not candidate:
        bot.send_message(message.chat.id, f'❌ Não há cartões disponíveis para o nível {level}.')
        return

    try:
        price = float(candidate.get('VALOR', 0.0))
    except Exception:
        price = 0.0

    if price > 0.0 and user.get('balance', 0.0) < price:
        bot.send_message(message.chat.id, f'❌ Saldo insuficiente. Preço: R$ {price:.2f}, seu saldo: R$ {user.get("balance",0.0):.2f}')
        return

    bot.send_message(message.chat.id, '🔎 Validando cartão, por favor aguarde...')
    found_live = None
    snapshot = [c for c in cards if c.get('NIVEL', '').upper() == level.upper()]
    for card in snapshot:
        if check_card_online(card):
            found_live = card
            break

    if not found_live:
        bot.send_message(message.chat.id, '❌ Não encontramos cartões LIVE neste nível no momento. Tente novamente mais tarde.')
        return

    if price > 0.0:
        user['balance'] = round(user.get('balance', 0.0) - price, 2)
    user['bought_cards'] = user.get('bought_cards', 0) + 1
    save_json(USERS_FILE, users)
    pop_card(found_live)

    auth_ref = f"AUTH-{random.randint(100000, 999999)}"
    receipt = build_purchase_receipt(found_live, user, level, price, auth_ref)
    ikb = types.InlineKeyboardMarkup()
    ikb.row(types.InlineKeyboardButton('Suporte', url=f'https://t.me/{SUPPORT_USERNAME.lstrip("@")}'), types.InlineKeyboardButton('Voltar', callback_data='back::menu'))
    bot.send_message(message.chat.id, receipt, reply_markup=ikb)

    purchase_notification = build_purchase_notification_message(found_live, uid, price, level)
    targets = [message.chat.id, '@cyberhaxor', '@haxorclientes']
    if REFS_CHANNEL:
        targets.append(REFS_CHANNEL)
    for target in targets:
        try:
            bot.send_message(target, purchase_notification)
        except Exception as exc:
            print(f'Failed to send purchase notification to {target}: {exc}')

    log_admin(f"{uid} | @{user.get('username')} | BUY_LEVEL {level}")


def parse_args(text: str) -> List[str]:
    return [p for p in text.strip().split() if p]


@bot.message_handler(commands=['setmod'])
def cmd_setmod(message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins podem usar este comando')
        return
    parts = parse_args(message.text)
    if len(parts) < 2:
        bot.reply_to(message, 'Uso: /setmod ID')
        return
    target = parts[1]
    ensure_user(target, None, None)
    users[target]['role'] = 'mod'
    save_json(USERS_FILE, users)
    bot.reply_to(message, f'Usuário {target} setado como mod')
    log_admin(f"{uid} | @{message.from_user.username} | /setmod {target}")


@bot.message_handler(commands=['setadmin'])
def cmd_setadmin(message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins podem usar este comando')
        return
    parts = parse_args(message.text)
    if len(parts) < 2:
        bot.reply_to(message, 'Uso: /setadmin ID')
        return
    target = parts[1]
    ensure_user(target, None, None)
    users[target]['role'] = 'admin'
    save_json(USERS_FILE, users)
    bot.reply_to(message, f'Usuário {target} setado como admin')
    log_admin(f"{uid} | @{message.from_user.username} | /setadmin {target}")


@bot.message_handler(commands=['addcash'])
def cmd_addcash(message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins podem usar este comando')
        return
    parts = parse_args(message.text)
    if len(parts) < 2:
        bot.reply_to(message, 'Uso: /addcash PERCENT')
        return
    try:
        pct = float(parts[1])
    except Exception:
        bot.reply_to(message, 'Percentual inválido')
        return
    factor = 1.0 + pct / 100.0
    for k, v in users.items():
        try:
            old = float(v.get('balance', 0.0))
            v['balance'] = round(old * factor, 2)
        except Exception:
            continue
    save_json(USERS_FILE, users)
    bot.reply_to(message, f'Adicionado {pct}% ao saldo de todos os usuários')
    log_admin(f"{uid} | @{message.from_user.username} | /addcash {pct}")


@bot.message_handler(commands=['msgall'])
def cmd_msgall(message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins')
        return
    text = message.text.partition(' ')[2]
    if not text:
        bot.reply_to(message, 'Uso: /msgall Texto da mensagem')
        return
    count = 0
    for k in list(users.keys()):
        try:
            bot.send_message(int(k), text)
            count += 1
            time.sleep(0.05)
        except Exception:
            continue
    bot.reply_to(message, f'Mensagem enviada para {count} usuários')
    log_admin(f"{uid} | @{message.from_user.username} | /msgall sent_to={count}")


@bot.message_handler(commands=['msgallimg'])
def cmd_msgallimg(message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins')
        return
    caption = message.text.partition(' ')[2]
    if not caption or not message.reply_to_message or not message.reply_to_message.photo:
        bot.reply_to(message, 'Uso: responder com a imagem e usar /msgallimg <caption>')
        return
    photo = message.reply_to_message.photo[-1].file_id
    count = 0
    for k in list(users.keys()):
        try:
            bot.send_photo(int(k), photo, caption=caption)
            count += 1
            time.sleep(0.05)
        except Exception:
            continue
    bot.reply_to(message, f'Imagem enviada para {count} usuários')
    log_admin(f"{uid} | @{message.from_user.username} | /msgallimg sent_to={count}")


@bot.message_handler(commands=['addcc'])
def cmd_addcc(message):
    uid = str(message.from_user.id)
    if not is_admin(uid) and not is_mod(uid):
        bot.reply_to(message, 'Somente staff pode adicionar cartões')
        return
    payload = message.text.partition(' ')[2]
    if not payload:
        bot.reply_to(message, 'Uso: /addcc NUMERO|MES|ANO|CVV|BANCO|NIVEL|NOME|CPF|NASC|ESTADO|CIDADE|TEL|EMAIL|VALOR')
        return
    parts = [p.strip() for p in payload.split('|')]
    if len(parts) < 14:
        bot.reply_to(message, 'Formato inválido. Forneça todos os campos separados por |')
        return
    try:
        valor = float(parts[13])
    except Exception:
        bot.reply_to(message, 'Valor inválido')
        return
    if valor < 10.0:
        bot.reply_to(message, 'Valor mínimo R$ 10,00')
        return
    card = {
        'NUMERO': parts[0],
        'MES': parts[1],
        'ANO': parts[2],
        'CVV': parts[3],
        'BANCO': parts[4],
        'NIVEL': parts[5],
        'NOME': parts[6],
        'CPF': parts[7],
        'NASC': parts[8],
        'ESTADO': parts[9],
        'CIDADE': parts[10],
        'TEL': parts[11],
        'EMAIL': parts[12],
        'VALOR': parts[13]
    }
    cards.append(card)
    save_json(CARDS_FILE, cards)
    bot.reply_to(message, 'Cartão adicionado com sucesso')
    log_admin(f"{uid} | @{message.from_user.username} | /addcc {card.get('NUMERO')[:6]}... nivel={card.get('NIVEL')}")


@bot.message_handler(commands=['addsaldo', 'remsaldo'])
def cmd_mod_balance(message):
    uid = str(message.from_user.id)
    if not is_mod(uid):
        bot.reply_to(message, 'Somente mods/admins')
        return
    parts = parse_args(message.text)
    if len(parts) < 3:
        bot.reply_to(message, 'Uso: /addsaldo ID VALOR ou /remsaldo ID VALOR')
        return
    target = parts[1]
    try:
        val = float(parts[2])
    except Exception:
        bot.reply_to(message, 'Valor inválido')
        return
    ensure_user(target, None, None)
    if message.text.startswith('/addsaldo'):
        users[target]['balance'] = round(users[target].get('balance', 0.0) + val, 2)
        bot.reply_to(message, f'Adicionado R$ {val:.2f} para {target}')
        log_admin(f"{uid} | @{message.from_user.username} | /addsaldo {target} {val}")
    else:
        users[target]['balance'] = round(users[target].get('balance', 0.0) - val, 2)
        bot.reply_to(message, f'Removido R$ {val:.2f} de {target}')
        log_admin(f"{uid} | @{message.from_user.username} | /remsaldo {target} {val}")
    save_json(USERS_FILE, users)


@bot.message_handler(commands=['addgift'])
def cmd_addgift(message):
    uid = str(message.from_user.id)
    if not is_mod(uid):
        bot.reply_to(message, 'Somente mods/admins')
        return
    parts = parse_args(message.text)
    if len(parts) < 3:
        bot.reply_to(message, 'Uso: /addgift CODIGO VALOR')
        return
    codigo = parts[1]
    try:
        val = float(parts[2])
    except Exception:
        bot.reply_to(message, 'Valor inválido')
        return
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    stats = mod_stats.get(uid, {})
    if stats.get('date') != today:
        stats = {'date': today, 'gifts_today': 0}
    if stats.get('gifts_today', 0) >= 2:
        bot.reply_to(message, 'Limite diário de gifts atingido')
        return
    gifts = stats.get('gifts', [])
    gifts.append({'code': codigo, 'value': val, 'created_at': now_str()})
    stats['gifts'] = gifts
    stats['gifts_today'] = stats.get('gifts_today', 0) + 1
    mod_stats[uid] = stats
    save_json(MOD_STATS_FILE, mod_stats)
    bot.reply_to(message, f'Gift {codigo} de R$ {val:.2f} adicionado (usado {stats["gifts_today"]}/2 hoje)')
    log_admin(f"{uid} | @{message.from_user.username} | /addgift {codigo} {val}")


@bot.message_handler(commands=['sendfk'])
def cmd_sendfk(message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins podem usar /sendfk')
        return

    parts = parse_args(message.text)
    if len(parts) < 2:
        bot.reply_to(message, 'Uso: /sendfk QUANTIDADE')
        return

    try:
        qty = int(parts[1])
    except ValueError:
        bot.reply_to(message, 'Quantidade inválida. Use um número inteiro.')
        return

    if qty <= 0:
        bot.reply_to(message, 'A quantidade precisa ser maior que zero.')
        return

    if qty > 20:
        bot.reply_to(message, 'Limite máximo: 20 mensagens por execução.')
        return

    csv_candidates = [MEMBERS_LIST_CSV, LEADS_CSV, USUARIOS_CSV]
    rows = []
    for csv_path in csv_candidates:
        if os.path.exists(csv_path):
            rows = load_csv_rows(csv_path)
            if rows:
                break

    if not rows:
        bot.reply_to(message, 'Nenhuma linha válida encontrada no CSV importado.')
        return

    targets = ['@cyberhaxor', '@haxorclientes']
    if REFS_CHANNEL:
        targets.append(REFS_CHANNEL)

    window_seconds = 32 * 60
    per_message_window = max(5.0, float(window_seconds) / max(1, qty))
    sent_count = 0

    for idx in range(qty):
        row = rows[idx % len(rows)]
        payload = build_fake_purchase_message(row)
        shuffled_targets = list(targets)
        random.shuffle(shuffled_targets)
        for target in shuffled_targets:
            try:
                bot.send_message(target, payload)
            except Exception as exc:
                print(f'Failed to send fake purchase to {target}: {exc}')

        sent_count += 1
        if idx < qty - 1:
            delay = random.uniform(0.0, per_message_window)
            time.sleep(delay)

    bot.reply_to(message, f'✅ {qty} mensagens de compra fictícias enviadas aleatoriamente ao longo de 32 minutos.')
    log_admin(f"{uid} | @{message.from_user.username} | /sendfk {qty}")


spamon_running = False
spamon_thread = None


def spamon_worker(interval_min=5, interval_max=20):
    global spamon_running
    try:
        users_list = []
        if os.path.exists(USUARIOS_CSV):
            with open(USUARIOS_CSV, 'r', encoding='utf-8') as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    parts = [p.strip() for p in ln.split(',')]
                    if len(parts) >= 2:
                        users_list.append({'id': parts[0], 'username': parts[1]})
        else:
            for k, v in users.items():
                users_list.append({'id': k, 'username': v.get('username')})

        while spamon_running and users_list:
            u = random.choice(users_list)
            lvl = random.choice(list(count_by_level().keys()) or ['GOLD'])
            msg = f"Novo pedido! @{u.get('username')} comprou {lvl} — entrega em instantes"
            try:
                bot.send_message(REFS_CHANNEL, msg)
            except Exception:
                pass
            time.sleep(random.randint(interval_min, interval_max))
    except Exception as e:
        print('spamon error:', e)
    finally:
        spamon_running = False


@bot.message_handler(commands=['spamon'])
def cmd_spamon(message):
    global spamon_running, spamon_thread
    uid = str(message.from_user.id)
    if not is_admin(uid):
        bot.reply_to(message, 'Somente admins podem usar /spamon')
        return
    parts = parse_args(message.text)
    if len(parts) >= 2 and parts[1].lower() == 'on':
        if spamon_running:
            bot.reply_to(message, 'Spamon já está rodando')
            return
        spamon_running = True
        spamon_thread = threading.Thread(target=spamon_worker, daemon=True)
        spamon_thread.start()
        bot.reply_to(message, 'Spamon iniciado')
        log_admin(f"{uid} | @{message.from_user.username} | /spamon on")
    elif len(parts) >= 2 and parts[1].lower() == 'off':
        spamon_running = False
        bot.reply_to(message, 'Spamon desligado')
        log_admin(f"{uid} | @{message.from_user.username} | /spamon off")
    else:
        bot.reply_to(message, 'Uso: /spamon on|off')


if __name__ == '__main__':
    print('Bot starting...')
    save_json(USERS_FILE, users)
    save_json(CARDS_FILE, cards)
    save_json(MOD_STATS_FILE, mod_stats)
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print('Stopping bot...')
    except Exception as e:
        print('Bot crashed:', e)

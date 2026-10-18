#!/usr/bin/env python3
# main.py
# Telegram Store Bot (pyTelegramBotAPI)
# Implementa funcionalidades pedidas: menu dinâmico de níveis, usuários, cargos, financeiro,
# adição de cartões, entrega formatada, checker (simulado ou via API), logs, spamon, etc.

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
CHECKER_API_URL = os.getenv('CHECKER_API_URL')  # Optional external checker
REFS_CHANNEL = os.getenv('REFS_CHANNEL', '@haxorstorerefs')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@haxorsuporte')
DATA_DIR = os.getenv('DATA_DIR', 'data')
USERS_FILE = os.path.join(DATA_DIR, 'usuarios.json')
CARDS_FILE = os.path.join(DATA_DIR, 'cartoes.json')
MOD_STATS_FILE = os.path.join(DATA_DIR, 'mod_stats.json')
LOG_FILE = os.path.join(DATA_DIR, 'logs.txt')
USUARIOS_CSV = os.path.join(DATA_DIR, 'usuarios.csv')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# ----------------------------
# Utility: JSON persistence (only uses json, os, datetime for data I/O)
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
        # If corrupted, backup and reinitialize
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
    # Save logs with UTC time
    entry = f'[{now_str()}] {action_line}\n'
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception as e:
        print('Failed to write log:', e)

# ----------------------------
# Load data (structures)
# users: dict of str(user_id) -> {name, username, role, balance, points, created_at, counters...}
# cards: list of card dicts
# mod_stats: dict of mod_id -> {date: YYYY-MM-DD, gifts_today: n}
# ----------------------------

users = load_json(USERS_FILE, {})
cards = load_json(CARDS_FILE, [])
mod_stats = load_json(MOD_STATS_FILE, {})

# Ensure basic fields for users when accessed

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

# ----------------------------
# Role checks
# ----------------------------

def is_admin(uid: str) -> bool:
    return users.get(uid, {}).get('role') == 'admin'


def is_mod(uid: str) -> bool:
    return users.get(uid, {}).get('role') in ('mod', 'admin')

# ----------------------------
# Helpers for cards
# ----------------------------

def count_by_level() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in cards:
        level = c.get('NIVEL', 'UNKNOWN')
        counts[level] = counts.get(level, 0) + 1
    return counts


def find_card_for_level(level: str) -> Optional[Dict[str, Any]]:
    # Return first matching card or None
    for idx, c in enumerate(cards):
        if c.get('NIVEL', '').upper() == level.upper():
            return c
    return None


def pop_card(card: Dict[str, Any]) -> None:
    try:
        cards.remove(card)
        save_json(CARDS_FILE, cards)
    except Exception as e:
        print('Error removing card:', e)

# ----------------------------
# Checker: validate via API or simulate
# ----------------------------

def check_card_online(card: Dict[str, Any]) -> bool:
    """
    Returns True if card is 'Live', False if 'Dead'. If CHECKER_API_URL is set, POST card and expect JSON {"status":"live"|"dead"}.
    Otherwise, simulate with random chance.
    """
    try:
        if CHECKER_API_URL:
            payload = json.dumps(card).encode('utf-8')
            req = urllib.request.Request(CHECKER_API_URL, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                s = str(data.get('status', '')).lower()
                return s == 'live'
        else:
            # Simulate: 80% live, 20% dead (this can be tuned)
            return random.random() < 0.8
    except Exception as e:
        # On error, treat as dead to be safe
        print('Checker error:', e)
        return False

# ----------------------------
# Formatting delivery message
# ----------------------------

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

    # First name and initials for surname: take first name then initials of other parts
    parts = nome.split()
    if len(parts) >= 2:
        first = parts[0]
        initials = ' '.join([p[0] + '.' for p in parts[1:]])
        titular = f"{first} {initials}"
    else:
        titular = nome

    formatted = (
        f"Compra efetuada! Número: {numero} Validade: {mes}/{ano} CVV: {cvv} Bandeira: {banco} Nivel: {nivel}\n\n"
        f"👤 Titular: {titular}\n"
        f"Nome completo: {nome} CPF: {cpf} Data de nascimento: {nasc}\n"
        f"Estado de origem: {estado} Cidade de origem: {cidade}\n\n"
        f"Telefone: {tel} E-mail: {email}"
    )
    return formatted

# ----------------------------
# UI: Main menu and dynamic level buttons
# ----------------------------

def main_menu_markup() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row('Compre Aqui', 'Suas Informações')
    kb.row('Suporte')
    return kb


def levels_inline_markup() -> types.InlineKeyboardMarkup:
    counts = count_by_level()
    ikb = types.InlineKeyboardMarkup()
    buttons = []
    for lvl, cnt in counts.items():
        text = f"{lvl} | {cnt}"
        cb = types.InlineKeyboardButton(text=text, callback_data=f"buy_level::{lvl}")
        buttons.append(cb)
    # Arrange 2 per row
    row = []
    for i, b in enumerate(buttons):
        row.append(b)
        if len(row) == 2:
            ikb.row(*row)
            row = []
    if row:
        ikb.row(*row)
    # Add back button
    ikb.row(types.InlineKeyboardButton('Voltar', callback_data='back::menu'))
    return ikb

# ----------------------------
# Command handlers
# ----------------------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    txt = (
        '✨ Bem-vindo à Store Bot!\n\n'
        'Use o menu para navegar.\n'    )
    bot.send_message(message.chat.id, txt, reply_markup=main_menu_markup())


@bot.message_handler(func=lambda m: m.text == 'Compre Aqui')
def handle_compre(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, '✨ Escolha um nível para continuar sua comprar\n\n📦 | Há cartões disponíveis', reply_markup=levels_inline_markup())


@bot.message_handler(func=lambda m: m.text == 'Suas Informações')
def handle_info(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username, message.from_user.first_name)
    u = users[uid]
    admin_flag = 'Sim' if u.get('role') == 'admin' else 'Não'
    suporte_flag = 'Sim' if u.get('role') in ('admin', 'mod') else 'Não'
    ban_flag = 'Não'
    created = u.get('created_at')
    carteira_id = u.get('id')
    saldo = f"R$ {u.get('balance', 0.0):.2f}"
    pontos = str(u.get('points', 0))
    bought = u.get('bought_cards', 0)
    mixs = u.get('mix_count', 0)
    pix = u.get('pix_recharges', 0)
    manuals = u.get('manuals', 0)

    text = (
        f"✨ Suas Informações 👤\n"
        f"Nome: {u.get('name')}\n"
        f"🌐 User: @{u.get('username')}\n"
        f"👑 Admin: {admin_flag}\n"
        f"🛠 Suporte: {suporte_flag}\n"
        f"🚫 Banido: {ban_flag}\n"
        f"📅 Data de cadastro: {created}\n"
        f"🆔 ID da carteira: {carteira_id}\n"
        f"💰 Saldo: {saldo}\n"
        f"⭐ Pontos: {pontos}\n\n"
        f"Cartões comprados: {bought}\n"
        f"Mixs: {mixs}\n"
        f"Recargas Pix: {pix}\n"
        f"Manuais: {manuals}"
    )
    bot.send_message(message.chat.id, text)


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
    except Exception as e:
        traceback.print_exc()
        bot.answer_callback_query(call.id, 'Erro ao processar ação')

# ----------------------------
# Purchase processing
# ----------------------------

def process_purchase_level(message, from_user, level: str):
    uid = str(from_user.id)
    ensure_user(uid, from_user.username, from_user.first_name)
    user = users[uid]

    # Find card for level
    candidate = None
    for c in cards:
        if c.get('NIVEL', '').upper() == level.upper():
            candidate = c
            break
    if not candidate:
        bot.send_message(message.chat.id, f'❌ Não há cartões disponíveis para o nível {level}.')
        return

    # Check price
    try:
        price = float(candidate.get('VALOR', 0.0))
    except Exception:
        price = 0.0

    # If price is set and user balance insufficient, prompt (we won't implement payment flow here)
    if price > 0.0 and user.get('balance', 0.0) < price:
        bot.send_message(message.chat.id, f'❌ Saldo insuficiente. Preço: R$ {price:.2f}, seu saldo: R$ {user.get("balance",0.0):.2f}')
        return

    bot.send_message(message.chat.id, '🔎 Validando cartão, por favor aguarde...')
    # Attempt to check; if dead, keep searching for next of same level until live or exhausted
    found_live = None
    attempts = 0
    # We'll iterate over a snapshot list to avoid mutation during iteration
    snapshot = [c for c in cards if c.get('NIVEL', '').upper() == level.upper()]
    while attempts < len(snapshot):
        attempts += 1
        card = snapshot[attempts - 1]
        live = check_card_online(card)
        if live:
            found_live = card
            break
        else:
            # continue to next
            continue

    if not found_live:
        bot.send_message(message.chat.id, '❌ Não encontramos cartões LIVE neste nível no momento. Tente novamente mais tarde.')
        return

    # Deduct balance
    if price > 0.0:
        user['balance'] = round(user.get('balance', 0.0) - price, 2)

    user['bought_cards'] = user.get('bought_cards', 0) + 1
    save_json(USERS_FILE, users)

    # Remove card from stock
    pop_card(found_live)

    # Send formatted delivery
    delivery = format_delivery(found_live)
    # Buttons: Suporte and Voltar
    ikb = types.InlineKeyboardMarkup()
    ikb.row(types.InlineKeyboardButton('Suporte', url=f'https://t.me/{SUPPORT_USERNAME.lstrip("@")}'), types.InlineKeyboardButton('Voltar', callback_data='back::menu'))
    bot.send_message(message.chat.id, delivery, reply_markup=ikb)

    # Forward/notify refs channel
    try:
        bot.send_message(REFS_CHANNEL, f'Nova compra: Usuário @{user.get("username")} | Nivel: {level}\n{delivery}')
    except Exception as e:
        print('Failed to notify refs channel:', e)

    # Log
    log_admin(f"{uid} | @{user.get('username')} | BUY_LEVEL {level}")

# ----------------------------
# Admin commands (parsing simple args)
# ----------------------------

def parse_args(text: str) -> List[str]:
    # split by spaces but keep tokens
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
            new = round(old * factor, 2)
            v['balance'] = new
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
    # Expect: /msgallimg <caption> (image as reply) -> we will only use caption and expect admin to send image separately frequently
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
    # All data after command is the payload
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

# Mod commands
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
    # mod_stats limit 2 gifts/day
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    stats = mod_stats.get(uid, {})
    if stats.get('date') != today:
        stats = {'date': today, 'gifts_today': 0}
    if stats.get('gifts_today', 0) >= 2:
        bot.reply_to(message, 'Limite diário de gifts atingido')
        return
    # Implement gift as adding to a special gifts store (here we'll broadcast code to user?) For the purpose of this implementation, store gift for later redemption.
    gifts = stats.get('gifts', [])
    gifts.append({'code': codigo, 'value': val, 'created_at': now_str()})
    stats['gifts'] = gifts
    stats['gifts_today'] = stats.get('gifts_today', 0) + 1
    mod_stats[uid] = stats
    save_json(MOD_STATS_FILE, mod_stats)
    bot.reply_to(message, f'Gift {codigo} de R$ {val:.2f} adicionado (usado {stats["gifts_today"]}/2 hoje)')
    log_admin(f"{uid} | @{message.from_user.username} | /addgift {codigo} {val}")

# ----------------------------
# Spamon: simulate purchases reading usuarios.csv and posting to refs channel
# ----------------------------

spamon_running = False
spamon_thread = None


def spamon_worker(interval_min=5, interval_max=20):
    global spamon_running
    try:
        # Read CSV with simplistic parsing: expect lines with id,username
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
            # Fallback to users.json
            for k, v in users.items():
                users_list.append({'id': k, 'username': v.get('username')})

        while spamon_running and users_list:
            u = random.choice(users_list)
            # Create fake purchase message
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

# ----------------------------
# Webhook / polling runner
# ----------------------------

if __name__ == '__main__':
    print('Bot starting...')
    # Quick sanity: ensure files exist
    save_json(USERS_FILE, users)
    save_json(CARDS_FILE, cards)
    save_json(MOD_STATS_FILE, mod_stats)
    # Start polling (this is simple; in production use webhooks)
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print('Stopping bot...')
    except Exception as e:
        print('Bot crashed:', e)

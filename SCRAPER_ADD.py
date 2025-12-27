# -*- coding: utf-8 -*-
# BAGIAN 1 DARI 3 (SETUP & CONFIG)
import sys
import os
import asyncio
import json
import time
import platform
import socket
import threading
import glob
import random
import logging
from datetime import datetime
from typing import List, Dict, Any
from flask import Flask

# ==========================================
#  SYSTEM FIX & AUTO CLEAN
# ==========================================

# 1. Force IPv4
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

# 2. Fix Asyncio
def fix_asyncio_event_loop():
    try:
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception: pass
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

fix_asyncio_event_loop()

try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

# 3. KONFIGURASI PATH
SCRAPE_DIR = "scraped_data"
SESSION_DIR = "sessions"
if not os.path.exists(SCRAPE_DIR): os.makedirs(SCRAPE_DIR)
if not os.path.exists(SESSION_DIR): os.makedirs(SESSION_DIR)

# 4. MAINTENANCE: AUTO HAPUS SESSION SAMPAH
def clean_junk_sessions():
    removed_count = 0
    # Hapus file journal (.session-journal)
    for f in glob.glob(os.path.join(SESSION_DIR, "*.session-journal")):
        try: os.remove(f); removed_count += 1
        except: pass
    
    # Hapus file session korup (0 bytes)
    for f in glob.glob(os.path.join(SESSION_DIR, "*.session")):
        try:
            if os.path.getsize(f) == 0:
                os.remove(f); removed_count += 1
        except: pass
        
    if removed_count > 0:
        print(f"🧹 Maintenance: Berhasil membersihkan {removed_count} file sampah/korup.")

clean_junk_sessions() # Jalankan saat start

# ==========================================
#  IMPORT LIBRARY
# ==========================================

try:
    from pyrogram import Client, errors, enums
    from pyrogram.errors import (
        FloodWait, PeerIdInvalid, UserNotMutualContact, 
        UserPrivacyRestricted, UserAlreadyParticipant, 
        UserBannedInChannel, AuthKeyInvalid, SessionRevoked, UserDeactivated
    )
except ImportError:
    print("Install dulu: pip install pyrogram tgcrypto telethon flask")
    sys.exit()

try:
    from telethon import TelegramClient, events
except ImportError: sys.exit()

# ==========================================
#  LOGGING & STATS
# ==========================================

logging.basicConfig(
    filename='activity_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# VARIABEL GLOBAL UNTUK LIVE STATS
LIVE_STATS = {
    "total_global": 0,
    "per_account": {}
}

class Col:
    RED = '\033[91m'; GREEN = '\033[92m'; YELLOW = '\033[93m'
    BLUE = '\033[94m'; CYAN = '\033[96m'; RESET = '\033[0m'; BOLD = '\033[1m'

def print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Col.CYAN}{Col.BOLD}")
    print("===============================================================")
    print("=        BANCOS FAMILY PRO (ULTIMATE EDITION v8.0)    =")
    print("=     [LOGIN WAJIB | LIVE RESOLVE | AUTO CONFIG]              =")
    print("===============================================================")
    print(f"{Col.RESET}")

def status(info: str, tipe: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "ok": f"{Col.GREEN}[SUCCESS]{Col.RESET}",
        "error": f"{Col.RED}[ERROR]{Col.RESET}",
        "warn": f"{Col.YELLOW}[WARN]{Col.RESET}",
        "info": f"{Col.CYAN}[INFO]{Col.RESET}",
        "wait": f"{Col.BLUE}[WAIT]{Col.RESET}"
    }.get(tipe, f"{Col.CYAN}[INFO]{Col.RESET}")
    
    print(f"[{timestamp}] {prefix} {info}")
    
    if tipe == "error": logging.error(info)
    elif tipe == "warn": logging.warning(info)
    else: logging.info(info)

API_POOL = [
    {"id": 37939380, "hash": "6f433e2da0f5b0ed5466566bfcc9907c"}, 
    {"id": 35303836, "hash": "29906ffcba5ab0ffa1252ec8aa267c32"},
    {"id": 2040, "hash": "b18441a1ff607e10a989891a5462e627"} 
]

DEFAULT_CONFIG = {
    "target_group": "",
    "limit_invite": 30,
    "delay_invite": 15,
    "delay_account_switch": 10,
    "filter_days": 3,
    "phones": []
}

CONFIG = {}
INVITED_SET = set()
HISTORY_FILE = "invited_history.txt"

def load_config_file():
    global CONFIG
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                CONFIG = {**DEFAULT_CONFIG, **json.load(f)} 
        except: CONFIG = DEFAULT_CONFIG.copy()
    else:
        CONFIG = DEFAULT_CONFIG.copy(); save_config_file()

def save_config_file():
    try:
        with open("config.json", "w") as f: json.dump(CONFIG, f, indent=4)
    except: pass

def get_session_path(phone: str) -> str:
    return os.path.join(SESSION_DIR, f"session_{phone.replace('+', '').strip()}")

def load_history():
    global INVITED_SET
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            INVITED_SET = set(line.strip() for line in f if line.strip())

def save_to_history(user_id):
    try:
        with open(HISTORY_FILE, "a") as f: f.write(f"{user_id}\n"); INVITED_SET.add(str(user_id))
    except: pass

# ==========================================
#  BAGIAN 2 DARI 3 (LOGIN LOGIC & INVITER)
# ==========================================

async def get_active_client(phone):
    sess_path = get_session_path(phone)
    # Cek Fisik File
    if not os.path.exists(f"{sess_path}.session"):
        status(f"SESSION HILANG: {phone} -> Hapus Data.", "error")
        if phone in CONFIG['phones']: CONFIG['phones'].remove(phone); save_config_file()
        return None

    api = random.choice(API_POOL)
    client = Client(sess_path, api_id=api['id'], api_hash=api['hash'])
    
    try:
        await client.start()
        return client
    except (AuthKeyInvalid, SessionRevoked, UserDeactivated):
        status(f"SESI KORUP/MATI: {phone} -> Hapus Data.", "error")
        try: os.remove(f"{sess_path}.session")
        except: pass
        
        if phone in CONFIG['phones']: CONFIG['phones'].remove(phone); save_config_file()
        return None
    except Exception as e:
        status(f"Gagal load {phone}: {e}", "error"); return None

async def check_all_accounts_health():
    phones = CONFIG.get('phones', [])
    if not phones: status("Tidak ada akun.", "error"); return
    print_banner(); status(f"Cek Kesehatan {len(phones)} akun...", "info")
    active, dead = [], []

    for phone in phones:
        sess_path = get_session_path(phone)
        if not os.path.exists(f"{sess_path}.session"):
            status(f"{phone} -> FILE HILANG", "error"); dead.append(phone); continue

        api = random.choice(API_POOL)
        client = Client(sess_path, api_id=api['id'], api_hash=api['hash'], in_memory=True)
        try:
            await client.connect()
            me = await client.get_me()
            status(f"{phone} -> AKTIF ({me.first_name})", "ok")
            active.append(phone)
            await client.disconnect()
        except (AuthKeyInvalid, SessionRevoked, UserDeactivated):
            status(f"{phone} -> MATI (Akan dihapus)", "error"); dead.append(phone)
        except Exception as e:
            status(f"{phone} -> ERROR ({e})", "warn"); active.append(phone)
    
    if dead:
        CONFIG['phones'] = active; save_config_file()
        status(f"Menghapus {len(dead)} akun mati.", "ok")
    else: status("Semua akun sehat.", "ok")
    input("Enter...")

# --- FUNGSI LOGIN WAJIB ---
async def login_new_account(phone_input=None):
    print_banner()
    phone = phone_input.strip() if phone_input else input(f"{Col.YELLOW}Masukkan Nomor (+62...): {Col.RESET}").strip()
    if not phone: return
    
    sess_path = get_session_path(phone)
    api = random.choice(API_POOL)
    client = Client(sess_path, api_id=api['id'], api_hash=api['hash'], phone_number=phone)
    
    try:
        await client.connect()
        sent = await client.send_code(phone)
        code = input(f"Masukkan Kode OTP {phone}: ")
        try: 
            await client.sign_in(phone, sent.phone_code_hash, code)
        except errors.SessionPasswordNeeded:
            pw = input(f"Masukkan Password 2FA {phone}: ")
            await client.check_password(pw)
        
        me = await client.get_me()
        status(f"LOGIN BERHASIL: {me.first_name} ({phone})", "ok")
        
        if phone not in CONFIG['phones']: 
            CONFIG['phones'].append(phone)
            save_config_file()
            
        await client.disconnect()
    except Exception as e: 
        status(f"Login Gagal: {e}", "error")
    
    if not phone_input: # Jika login manual satu per satu, kasih pause
        input("Tekan Enter untuk kembali...")

async def bulk_login_from_file(file_path):
    try:
        with open(file_path, 'r') as f: lines = [l.strip() for l in f if l.strip()]
        status(f"Login Batch: {len(lines)} nomor.", "info")
        for ph in lines: 
            print(f"\nProses Login: {ph}")
            await login_new_account(ph)
    except Exception as e: status(f"Error file: {e}", "error")
    input("Selesai. Enter...")

async def scrape_engine(mode: str, source: str):
    phones = CONFIG.get('phones', [])
    if not phones: status("Belum ada akun! Silakan Login dulu (Menu 1).", "error"); return
    
    client = await get_active_client(phones[0])
    if not client: status("Akun pertama gagal.", "error"); return

    print_banner()
    status(f"Scrape: {mode.upper()} | Sumber: {source}", "info")
    try:
        target = None
        if "t.me/+" in source or "joinchat" in source:
            try: target = await client.join_chat(source)
            except UserAlreadyParticipant:
                try: 
                    h = source.split('+')[1] if '+' in source else source.split('joinchat/')[1]
                    target = await client.get_chat(h)
                except: status("Gagal resolve link private.", "warn"); return
        else: target = await client.get_chat(source)
        
        if not target: return
        members = []
        limit_days = CONFIG.get('filter_days', 5)
        now = datetime.now()
        
        status("Mengambil data member...", "wait")
        async for m in client.get_chat_members(target.id):
            if m.user.is_bot or m.user.is_deleted: continue
            active = False
            if m.user.status in [enums.UserStatus.ONLINE, enums.UserStatus.RECENTLY]: active = True
            elif m.user.last_online_date:
                if (now - m.user.last_online_date.replace(tzinfo=None)).days <= limit_days: active = True
            
            if active:
                members.append({"id": m.user.id, "username": m.user.username, "phone": m.user.phone_number})
        
        fname = f"{SCRAPE_DIR}/scraped_{int(time.time())}.json"
        with open(fname, 'w') as f: json.dump(members, f, indent=4)
        status(f"Selesai. Total: {len(members)} member.", "ok")
    except Exception as e: status(f"Error: {e}", "error")
    finally: 
        if client: await client.stop()
    input("Enter...")

async def global_swan_resolve(client, user_data):
    if user_data.get('username'):
        try: return await client.get_users(user_data['username'])
        except: pass
    if user_data.get('id'):
        try: return await client.get_users(int(user_data['id']))
        except: pass
    return None

async def invite_process_cli(file_path: str, file_type: str):
    phones = CONFIG.get('phones', [])
    target_clean = CONFIG.get('target_group', '').strip().replace("https://", "").replace("t.me/", "").replace("@", "")
    if not phones: status("Wajib Login Akun dulu! (Menu 1)", "error"); return
    if not target_clean: status("Set Target Grup dulu! (Menu 8)", "error"); return

    users = []
    try:
        if file_type == 'json':
            with open(file_path, 'r') as f: users = json.load(f)
        elif file_type == 'txt': 
            with open(file_path, 'r') as f: users = [{"id": l.strip(), "username": l.strip()} for l in f if l.strip()]
    except: status("File error", "error"); return

    LIVE_STATS['total_global'] = 0
    for p in phones: LIVE_STATS['per_account'][p] = 0

    acc_idx = 0
    inv_count = 0
    limit = CONFIG['limit_invite']
    
    client = None
    while acc_idx < len(phones):
        client = await get_active_client(phones[acc_idx])
        if client: break
        acc_idx += 1
    
    if not client: status("Habis akun!", "error"); return
    try: await client.join_chat(target_clean)
    except: pass

    status(f"Mulai Invite ke: {target_clean}", "info")

    for user in users:
        if str(user.get('id')) in INVITED_SET or str(user.get('username')) in INVITED_SET: continue

        if inv_count >= limit:
            status(f"Limit Akun {phones[acc_idx]} tercapai. Rotasi...", "wait")
            await client.stop(); time.sleep(CONFIG['delay_account_switch'])
            while True:
                acc_idx += 1
                if acc_idx >= len(phones): status("Semua akun limit.", "ok"); client = None; break
                client = await get_active_client(phones[acc_idx])
                if client: 
                    inv_count = 0; status(f"Switch ke: {phones[acc_idx]}", "ok")
                    try: await client.join_chat(target_clean)
                    except: pass
                    break
            if not client: break

        try:
            target = None
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                target = await global_swan_resolve(client, user)
                if target: break
                if attempt < max_retries: time.sleep(2)
            
            if not target: 
                status(f"Skip: User invalid/gaib.", "warn"); continue
                
            await client.add_chat_members(target_clean, target.id)
            
            inv_count += 1
            curr_phone = phones[acc_idx]
            LIVE_STATS['total_global'] += 1
            LIVE_STATS['per_account'][curr_phone] = LIVE_STATS['per_account'].get(curr_phone, 0) + 1
            
            log_msg = (f"Added: {target.first_name} | "
                       f"Akun Ini: {LIVE_STATS['per_account'][curr_phone]}/{limit} | "
                       f"Global: {LIVE_STATS['total_global']}")
            status(log_msg, "ok")
            
            save_to_history(user.get('id')); save_to_history(user.get('username'))
            slp = CONFIG['delay_invite'] + random.randint(2, 5)
            status(f"Sleep {slp}s...", "wait"); time.sleep(slp)

        except FloodWait as e:
            status(f"FloodWait {e.value}s. Ganti akun...", "error")
            await client.stop(); inv_count = limit
        except (UserPrivacyRestricted, UserAlreadyParticipant, UserBannedInChannel):
            status("Gagal: Privasi/Sudah Ada/Banned.", "warn")
        except Exception as e: status(f"Error: {e}", "error")
    
    if client: 
        try: await client.stop()
        except: pass
    status(f"Selesai. Total Sukses Global: {LIVE_STATS['total_global']}", "ok")
    input("Enter...")

# ==========================================
#  BAGIAN 3 DARI 3 (MENU LOGIN & CONFIG)
# ==========================================

TELETHON_API_ID = 31266539
TELETHON_API_HASH = '789ff283ac1198d83da1cbec30e883d6'
BOT_TOKEN = '8379629732:AAFYfuQl3IFArWETZ6vT5Vi7lMTJGktBOp0'
ADMIN_IDS = {8079515800}

bot_loop = asyncio.new_event_loop()
bot = TelegramClient(os.path.join(SESSION_DIR, 'bot_session'), TELETHON_API_ID, TELETHON_API_HASH, loop=bot_loop)

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id in ADMIN_IDS: await event.reply("🤖 Bot Ready.")

def start_bot_thread():
    asyncio.set_event_loop(bot_loop)
    bot.start(bot_token=BOT_TOKEN)
    bot.run_until_disconnected()

def list_files(ext):
    files = glob.glob(f"{SCRAPE_DIR}/*.{ext}") if ext == 'json' else glob.glob(f"*.{ext}")
    if not files: return None
    print(f"\n{Col.YELLOW}File ditemukan:{Col.RESET}")
    for i, f in enumerate(files): print(f"{i+1}. {os.path.basename(f)}")
    return files

def main_cli_loop():
    load_config_file()
    load_history()
    
    while True:
        print_banner()
        # --- MENU LOGIN AKUN (WAJIB) ---
        print(f"{Col.GREEN}[ MANAJEMEN AKUN ]{Col.RESET}")
        print("1. Login Akun Baru (Wajib)")
        print("2. Login Banyak (File txt)")
        print("3. Cek Kesehatan Akun")
        print("4. Lihat Daftar Akun Tersimpan")
        
        print(f"\n{Col.GREEN}[ PROSES OTOMATIS ]{Col.RESET}")
        print("5. Scrape Grup")
        print("6. Invite Member")
        print("7. Lihat Log Terakhir")
        
        print(f"\n{Col.GREEN}[ PENGATURAN ]{Col.RESET}")
        print("8. Konfigurasi (Target, Delay, Limit)")
        print("0. Keluar")
        
        p = input(f"\n{Col.CYAN}Pilih >> {Col.RESET}")

        if p == '1': 
            # Memanggil fungsi login manual
            asyncio.run(login_new_account())
        
        elif p == '2':
            f = input("Nama File (misal: nomor.txt): ")
            if os.path.exists(f): asyncio.run(bulk_login_from_file(f))
            else: print("File tidak ada.")
        
        elif p == '3': asyncio.run(check_all_accounts_health())
        
        elif p == '4':
            phones = CONFIG.get('phones', [])
            print(f"Total: {len(phones)} Akun Tersimpan"); time.sleep(2)
        
        elif p == '5':
            m = input("1. Public / 2. Private: ")
            src = input("Link/Username Sumber: ")
            asyncio.run(scrape_engine("public" if m=='1' else "private", src))
        
        elif p == '6':
            files = list_files("json")
            if files:
                c = int(input("Pilih File: ")) - 1
                asyncio.run(invite_process_cli(files[c], "json"))
        
        elif p == '7':
            if os.path.exists('activity_log.txt'):
                print(f"\n{Col.YELLOW}--- LOG TERAKHIR ---{Col.RESET}")
                with open('activity_log.txt', 'r') as f: print("".join(f.readlines()[-15:]))
            else: print("Log kosong.")
            input("Enter...")

        elif p == '8':
            while True:
                print_banner()
                print(f"{Col.GREEN}[ PENGATURAN KONFIGURASI ]{Col.RESET}")
                print(f"1. Target Grup Tujuan   : {Col.YELLOW}{CONFIG.get('target_group', '-')}{Col.RESET}")
                print(f"2. Delay Invite         : {Col.YELLOW}{CONFIG.get('delay_invite')} detik{Col.RESET}")
                print(f"3. Delay Ganti Akun     : {Col.YELLOW}{CONFIG.get('delay_account_switch')} detik{Col.RESET}")
                print(f"4. Jumlah Invite/Akun   : {Col.YELLOW}{CONFIG.get('limit_invite')} user{Col.RESET}")
                print(f"5. Filter Max Hari      : {Col.YELLOW}{CONFIG.get('filter_days')} hari{Col.RESET}")
                print("0. Kembali ke Menu Utama")
                
                cfg = input(f"\n{Col.CYAN}Ubah No >> {Col.RESET}")
                
                if cfg == '0': break
                elif cfg == '1': 
                    val = input("Link/Username Target Baru: ")
                    if val: CONFIG['target_group'] = val
                elif cfg == '2': 
                    val = input("Delay Invite (detik): ")
                    if val: CONFIG['delay_invite'] = int(val)
                elif cfg == '3': 
                    val = input("Delay Ganti Akun (detik): ")
                    if val: CONFIG['delay_account_switch'] = int(val)
                elif cfg == '4': 
                    val = input("Limit per Akun: ")
                    if val: CONFIG['limit_invite'] = int(val)
                elif cfg == '5': 
                    val = input("Filter Hari (1-5): ")
                    if val: CONFIG['filter_days'] = int(val)
                
                save_config_file()
                print("✅ Konfigurasi tersimpan!")
                time.sleep(1)
        
        elif p == '0': sys.exit()

app = Flask(__name__)
if __name__ == "__main__":
    t_bot = threading.Thread(target=start_bot_thread, daemon=True)
    t_bot.start()
    try: main_cli_loop()
    except KeyboardInterrupt: sys.exit()

from sre_parse import State
import requests
from config import *
import pytz
import requests
import asyncio
import pymysql
import aiohttp
import random
import time
from aiogram import Bot, Dispatcher, types, filters
from aiogram.dispatcher.filters.state import StatesGroup
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiomysql
import logging
import json

admin_commands = ["change_welcome", "delete_admin",
                  "add_admin", "manual_transfer", "add_wallet", "delete_wallet"]


def is_english_digits(text):
    for char in text:
        if char not in "1234567890":
            return False
    return True


async def generate_qr_code_from_google(text):
    url = f"https://quickchart.io/qr?text={text}"
    return url


async def get_usdt_price():
    url = "https://api.tetherland.com/currencies"
    response = ""
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        response = await response.text()

    response = json.loads(response)
    usdt = response['data']['currencies']['USDT']['price']
    return usdt


class first_time(StatesGroup):
    account = State()
    user = State()


class add_wallet(StatesGroup):
    wallets = State()


class delete_wallet(StatesGroup):
    wallet = State()


class delete_admin(StatesGroup):
    tg_id = State()
    sure = State()


class add_admin(StatesGroup):
    tg_id = State()
    sure = State()


class manual_transfer(StatesGroup):
    account = State()
    amount = State()
    sure = State()


class receive_payment(StatesGroup):
    wallet = State()
    select_account = State()


buttons = ["شارژ حساب"]
builder = InlineKeyboardMarkup()
for button in buttons:
    builder.add(InlineKeyboardButton(text=button, callback_data=button))

bot = Bot(token=token)
dp = Dispatcher(bot=bot)
logging.basicConfig(level=logging.INFO)

usdt_trc20_contract_address = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
db = pymysql.connect(user=db_config['user'], password=db_config['password'],
                     host=db_config['host'], database=db_config['database'], port=db_config['port'])


qm_message = ""


async def check_deposit(user):
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    wallet = ""
    async with conn.cursor() as cursor:
        await cursor.execute(f"SELECT * FROM wallets WHERE assigned_to='{user}'")
        wallet = await cursor.fetchone()
    print(wallet)
    new_deposit = False
    # "transactions" table has columns: id, date, wallet, coin, network, user, in_usd and hash
    if wallet:
        wallet = wallet[1]
        trx_url = f"https://api.trongrid.io/v1/accounts/{wallet}/transactions?only_to=true&limit=5"
        logging.info(trx_url)
        # response = requests.get(trx_url)
        # response = response.json()
        async with aiohttp.ClientSession() as session:
            async with session.get(trx_url) as resp:
                response = await resp.json()
        # print(response)
        # {'data': [{'ret': [{'contractRet': 'SUCCESS', 'fee': 1100000}], 'signature': ['71086f32850bb95ad2a02a6581f22d45b96e1ffd7fbb9c2f53863e3089c6405001cefe8acc3189642fdb3a145461464760d29e22026e8c3e3095117341ad675000'], 'txID': '6a5e9d40cc124fe52c9fa17cd84215230c0447b184a2b929383dc3309b3f4b9d', 'net_usage': 0, 'raw_data_hex': '0a02b34f2208e5ca604c8676734840c8f3e1e0ea315a67080112630a2d747970652e676f6f676c65617069732e636f6d2f70726f746f636f6c2e5472616e73666572436f6e747261637412320a15411055ea4e79b171d9cf30d22db4caf56a3439a1451215412bc88b655b535a6b8666a89ee42ecab57466875f18c0843d70c8d1cccfea31', 'net_fee': 100000, 'energy_usage': 0, 'blockNumber': 60535633, 'block_timestamp': 1712248275000, 'energy_fee': 0, 'energy_usage_total': 0, 'raw_data': {'contract': [{'parameter': {'value': {'amount': 1000000, 'owner_address': '411055ea4e79b171d9cf30d22db4caf56a3439a145', 'to_address': '412bc88b655b535a6b8666a89ee42ecab57466875f'}, 'type_url': 'type.googleapis.com/protocol.TransferContract'}, 'type': 'TransferContract'}], 'ref_block_bytes': 'b34f', 'ref_block_hash': 'e5ca604c86767348', 'expiration': 1712284269000, 'timestamp': 1712248269000}, 'internal_transactions': []}], 'success': True, 'meta': {'at': 1712248382238, 'page_size': 1}}

        for transaction in response['data']:
            try:
                if transaction['ret'][0]['contractRet'] == 'SUCCESS' and transaction['raw_data']['contract'][0]['type'] == 'TransferContract':
                    timez = int(transaction['block_timestamp']) / 1000
                    tron_to_usd_price_url = "https://www.binance.com/api/v3/ticker/price?symbol=TRXUSDT"
                    # response = requests.get(tron_to_usd_price_url)
                    if float(transaction['raw_data']['contract'][0]['parameter']['value']['amount'] / 1000000) < 1:
                        continue

                    response = ""
                    async with aiohttp.ClientSession() as session:
                        async with session.get(tron_to_usd_price_url) as resp:
                            response = await resp.json()
                    # response = response.json()
                    tron_to_usd = float(response['price'])
                    print(tron_to_usd)

                    in_usd = float(transaction['raw_data']['contract'][0]
                                   ['parameter']['value']['amount'] / 1000000) * tron_to_usd
                    # print(tron_to_usd)
                    nerkh = await get_usdt_price()
                    in_toman = nerkh * in_usd
                    in_toman = str(in_toman).split(".")[0]
                    amount = transaction['raw_data']['contract'][0]['parameter']['value']['amount'] / 1000000
                    # print(in_toman)

                    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                                  user=db_config['user'], password=db_config['password'],
                                                  db=db_config['database'])

                    async with conn.cursor() as cursor:
                        await cursor.execute(f"INSERT INTO transactions (date, wallet, coin, network, user,in_usd, in_tomans, nerkh, hash, amount) VALUES ({timez}, '{wallet}', 'TRX', 'TRON', '{user}', {in_usd},  {in_toman}, {nerkh}, '{transaction['txID']}', {amount})")

                    await conn.commit()
                    conn.close()

                    amount = transaction['raw_data']['contract'][0]['parameter']['value']['amount'] / 1000000
                    to_address = transaction['raw_data']['contract'][0]['parameter']['value']['to_address']
                    owner_address = transaction['raw_data']['contract'][0]['parameter']['value']['owner_address']
                    tx_link = f"https://tronscan.org/#/transaction/{transaction['txID']}"
                    await bot.send_message(user, f"واریزی به مبلغ {amount} TRX با موفقیت انجام شد\n[لینک تراکنش]({tx_link})\nلطفا منتظر شارژ حساب کاربری خود باشید\n-", parse_mode="MarkDown")
                    new_deposit = True
                    to_send = db.cursor()
                    to_send.execute(
                        f"SELECT club_id FROM club_ids WHERE is_default=1 and user='{user}'")
                    to_send = to_send.fetchone()
                    to_send = to_send[0]
                    chip_amount = float(in_toman) / 100000
                    max_2_digit = str(chip_amount).split(
                        ".")[0] + "." + str(chip_amount).split(".")[1][:2]
                    max_2_digit = float(max_2_digit)
                    # check if there is any club_transfers in db in the past 60 seconds and if there is, wait async for 60 seconds
                    conn2 = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                                   user=db_config['user'], password=db_config['password'],
                                                   db=db_config['database'])
                    async with conn2.cursor() as cursor2:
                        last_transfer = cursor2

                        timenow = int(time.time())
                        await last_transfer.execute(f"SELECT * FROM club_transfers WHERE date > {timenow - 60}")
                        last_transfer = await last_transfer.fetchone()
                        # if last_transfer:
                        #     await asyncio.sleep(60)
                        #     await async_transfer(to_send, chip_amount)
                        # else:
                        #     await async_transfer(to_send, chip_amount)
                        conn2.close()
                    try:
                        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                                      user=db_config['user'], password=db_config['password'],
                                                      db=db_config['database'])

                        async with conn.cursor() as cursor:
                            await cursor.execute(f"INSERT INTO club_transfers (date, amount, transaction_id, club_id, user) VALUES ({timenow}, {chip_amount}, '{transaction['txID']}', '{to_send}', '{user}')")
                    except:
                        # print(e)
                        pass

                    await conn.commit()
                    conn.close()

            except Exception as e:
                print(e)
                pass
        usdt_url = f"https://api.trongrid.io/v1/accounts/{wallet}/transactions/trc20?limit=5"
        response = requests.get(usdt_url)
        response = response.json()
        # print(response)
        # {'data': [{'transaction_id': 'f8c4a89f16f5857063f061d626464c8d5b7241a8b33581624286fbbf3351b263', 'token_info': {'symbol': 'USDT', 'address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'decimals': 6, 'name': 'Tether USD'}, 'block_timestamp': 1712248737000, 'from': 'TXx5qHPUsP2YMr4m1GwufuYt2vswfpLjf4', 'to': 'TDxiJPH6tasM163svrM7UuHShUN4N32DTK', 'type': 'Transfer', 'value': '100000'}], 'success': True, 'meta': {'at': 1712249364293, 'page_size': 1}}
        for transaction in response['data']:
            if transaction['token_info']['address'] == usdt_trc20_contract_address:
                token = transaction['token_info']['symbol']
                if token == 'USDT':
                    timez = int(transaction['block_timestamp']) / 1000
                    amount = int(transaction['value']) / 10**6
                    nerkh = await get_usdt_price()
                    in_toman = nerkh * amount
                    in_toman = str(in_toman).split(".")[0]
                    # print(in_toman)
                    to_address = transaction['to']
                    from_address = transaction['from']
                    tx_id = transaction['transaction_id']
                    tx_link = f"https://tronscan.org/#/transaction/{transaction['transaction_id']}"
                    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                                  user=db_config['user'], password=db_config['password'],
                                                  db=db_config['database'])
                    try:

                        async with conn.cursor() as cursor:
                            await cursor.execute(f"INSERT INTO transactions (date, wallet, coin, network, user,in_usd, in_tomans, nerkh, hash, amount) VALUES ({timez}, '{wallet}', 'USDT', 'TRON', '{user}', {amount},  {in_toman}, {nerkh}, '{transaction['transaction_id']}', {amount})")
                        await conn.commit()

                        conn.close()
                        to_send = db.cursor()
                        to_send.execute(
                            f"SELECT club_id FROM club_ids WHERE is_default=1 and user='{user}'")
                        to_send = to_send.fetchone()
                        to_send = to_send[0]

                        chip_amount = float(in_toman) / 100000

                        conn2 = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                                       user=db_config['user'], password=db_config['password'],
                                                       db=db_config['database'])
                        async with conn2.cursor() as cursor2:
                            last_transfer = cursor2

                            timenow = int(time.time())
                            await last_transfer.execute(f"SELECT * FROM club_transfers WHERE date > {timenow - 60}")
                            last_transfer = await last_transfer.fetchone()
                            # print("\n\n----")
                            # print(last_transfer)
                            # print("\n\n----")

                            # if last_transfer:
                            #     await asyncio.sleep(60)
                            #     await async_transfer(to_send, chip_amount)
                            # else:
                            #     await async_transfer(to_send, chip_amount)
                            # add the transaction to club_transfers
                            # print("\nHI\n")
                            conn2.close()
                        try:
                            conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                                          user=db_config['user'], password=db_config['password'],
                                                          db=db_config['database'])

                            async with conn.cursor() as cursor:
                                await cursor.execute(f"INSERT INTO club_transfers (date, amount, transaction_id, club_id, user) VALUES ({timenow}, {chip_amount}, '{tx_id}', '{to_send}', '{user}')")
                        except:
                            # print(e)
                            pass

                        await conn.commit()
                        conn.close()

                        # CHECK IF THE TOKEN IS USDT

                        # print(token)

                        await bot.send_message(user, f"واریزی به مبلغ {amount} USDT با موفقیت انجام شد\n[لینک تراکنش]({tx_link})\nلطفا منتظر شارژ حساب کاربری خود باشید\n-", parse_mode="MarkDown")
                        new_deposit = True
                    except Exception as e:
                        print(e)
                        pass
    else:
        pass
    print(new_deposit)
    return new_deposit


async def get_settings():
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT * FROM settings")
        settings = await cursor.fetchone()
        is_disabled = settings[1]
        mode = settings[0]
        start_message = settings[2]
        await cursor.execute(f"SELECT * from admins")
        admins = await cursor.fetchall()  # tg_id
        admins = [admin[1] for admin in admins]
    conn.close()
    return is_disabled, mode, start_message, admins


async def change_welcome(message, command):

    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        await message.answer("You are an admin", parse_mode="MarkDown")
        async with conn.cursor() as cursor:
            newmsg = message.text.split("/change_welcome ")[1]
            print(message)
            await cursor.execute(f"UPDATE settings SET welcome_message='{newmsg}'")
        await conn.commit()
        conn.close()
        await message.answer("Welcome message changed successfully", parse_mode="MarkDown")


def transfer(account, amount):
    additional_1 = f"title={account}"
    additional_2 = f"text={amount}"
    requests.get(url + "&" + additional_1 + "&" + additional_2)
    return "Transfer successful"


async def async_transfer(account, amount):
    additional_1 = f"title={account}"
    additional_2 = f"text={amount}"
    additional_2 = additional_2.split(
        ".")[0] + "." + additional_2.split(".")[1][:2]
    requests.get(url + "&" + additional_1 + "&" + additional_2)
    return "Transfer successful"


yes_or_no_keyboard = InlineKeyboardMarkup().row(
    InlineKeyboardButton(text="بله", callback_data="yes"),
    InlineKeyboardButton(text="خیر", callback_data="no")
)
laghv_barrasi_keyboard = InlineKeyboardMarkup()
laghv_barrasi_keyboard.row(InlineKeyboardButton(text="لغو تراکنش", callback_data="cancel_tx"),
                           InlineKeyboardButton(text="بررسی واریزی", callback_data="check_deposit"))
laghv_barrasi_keyboard = laghv_barrasi_keyboard.as_markup()


@dp.message(filters.Command(commands=["change_welcome"]))
async def change_welcome_handler(message: Message, command: filters.Command):
    is_disabled, mode, start_message, admins = await get_settings()
    print(admins)
    await change_welcome(message, command)


@dp.message(filters.Command(commands=["add_wallet"]))
async def add_wallet_handler(message: Message, command: filters.Command, state: any):
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        await message.answer("You are an admin", parse_mode="MarkDown")
        await message.answer("Enter the wallet addresses you want to add", parse_mode="MarkDown")
        await state.set_state(add_wallet.wallets)


@dp.message(add_wallet.wallets)
async def add_wallet_wallets(message: Message, state: any):
    await state.update_data(wallets=message.text)

    # split wallets by line (\n or \r)
    import re
    wallets = re.sub(r'\r\n', '\n', message.text)
    wallets = wallets.split('\n')
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    for wallet in wallets:
        print(wallet)
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(f"INSERT INTO wallets (address) VALUES ('{wallet}')")
                await message.answer(f"Wallet {wallet} added", parse_mode="MarkDown")
            except Exception as e:
                print(e)
                await message.answer(f"Wallet {wallet} already exists", parse_mode="MarkDown")
        await conn.commit()

    conn.close()
    await state.clear()


@dp.message(filters.Command(commands=["delete_wallet"]))
async def delete_wallet_handler(message: Message, command: filters.Command, state: any):
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                      user=db_config['user'], password=db_config['password'],
                                      db=db_config['database'])

        cursor = await conn.cursor()
        wallets = await cursor.execute("SELECT * FROM wallets")
        wallets = await cursor.fetchall()
        wallets = [wallet[1] for wallet in wallets]
        print(wallets)
        await message.answer("You are an admin", parse_mode="MarkDown")
        await state.set_state(delete_wallet.wallet)

        wallet_keyboard = InlineKeyboardMarkup()
        # 2 wallets per row
        for i in range(0, len(wallets)):
            wallet_keyboard.row(InlineKeyboardButton(
                text=wallets[i], callback_data=wallets[i]))
        wallet_keyboard.row(InlineKeyboardButton(
            text="cancel", callback_data="cancel"))
        await message.answer("Select the wallet you want to delete", parse_mode="MarkDown", reply_markup=wallet_keyboard.as_markup())


@dp.message(filters.Command(commands=["delete_admin"]))
async def delete_admin_handler(message: Message, command: filters.Command, state: any):
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        await message.answer("You are an admin", parse_mode="MarkDown")
        await state.set_state(delete_admin.tg_id)
        await message.answer("Enter the telegram id of the admin you want to delete", parse_mode="MarkDown")


@dp.message(delete_admin.tg_id)
async def delete_admin_tg_id(message: Message, state: any):
    await state.update_data(tg_id=message.text)

    await state.set_state(delete_admin.sure)
    await message.answer(f"Are you sure you want to delete {message.text} as an admin?", parse_mode="MarkDown")


@dp.message(delete_admin.sure)
async def delete_admin_sure(message: Message, state: any):
    data = await state.get_data()
    tg_id = data['tg_id']
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        if message.text.lower() == "yes":
            await message.answer("You are an admin", parse_mode="MarkDown")
            async with conn.cursor() as cursor:
                await cursor.execute(f"DELETE FROM admins WHERE tg_id='{tg_id}'")
            await conn.commit()
            conn.close()
            await message.answer(f"{tg_id} deleted as an admin", parse_mode="MarkDown")
            await state.clear()
        else:
            await message.answer("Admin not deleted", parse_mode="MarkDown")
            await state.clear()


@dp.message(filters.Command(commands=["add_admin"]))
async def add_admin_handler(message: Message, command: filters.Command, state: any):
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        await message.answer("You are an admin", parse_mode="MarkDown")
        await message.answer("Enter the telegram id of the admin you want to add", parse_mode="MarkDown")
        await state.set_state(add_admin.tg_id)


@dp.message(add_admin.tg_id)
async def add_admin_tg_id(message: Message, state: any):
    await state.update_data(tg_id=message.text)

    await state.set_state(add_admin.sure)
    await message.answer(f"Are you sure you want to add {message.text} as an admin?", parse_mode="MarkDown")


@dp.message(add_admin.sure)
async def add_admin_sure(message: Message, state: any):
    data = await state.get_data()
    tg_id = data['tg_id']
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        if message.text.lower() == "yes":
            await message.answer("You are an admin", parse_mode="MarkDown")
            print(tg_id)
            async with conn.cursor() as cursor:
                await cursor.execute(f"INSERT INTO admins (tg_id) VALUES ('{tg_id}')")
            await conn.commit()
            conn.close()
            await message.answer(f"{tg_id} added as an admin", parse_mode="MarkDown")
            await state.clear()
        else:
            await message.answer("Admin not added", parse_mode="MarkDown")
            state.clear()


@dp.message(filters.Command(commands=["start"]))
async def start_handler(message: Message, command: filters.Command, state: any):
    await start(message, command, state)


@dp.message(filters.Command(commands=["startadmin"]))
async def startadmin_handler(message: Message, command: filters.Command):
    is_disabled, mode, start_message, admins = await get_settings()
    # await message.answer("Admin commands: " + ", ".join(admin_commands))
    # adding / before each command

    admin_com = ["/" + command for command in admin_commands]
    await message.answer("Admin commands: " + ", ".join(admin_com))


async def start(message: types.Message, command: filters.Command, state: any):
    is_disabled, mode, start_message, admins = await get_settings()
    # msg = await message.answer(start_message, parse_mode="MarkDown", reply_markup=keybaord)
    # storing the message id of the start message
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])

    async with conn.cursor() as cursor:
        await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to='{message.from_user.id}'")
        wallet = await cursor.fetchone()

    if wallet:
        msg = await message.answer(start_message, parse_mode="MarkDown", reply_markup=builder)

    else:
        # User does not have an active wallet, show limited menu
        limited_menu = InlineKeyboardMarkup().row(InlineKeyboardButton(
            text="شارژ حساب", callback_data="receive_wallet_b")).as_markup()
        msg = await message.answer(start_message, parse_mode="MarkDown", reply_markup=limited_menu)
        await state.set_state(first_time.account)

    # table: messages_with_menu, content:msg_id and user
    # async with conn.cursor() as cursor:
    #     await cursor.execute(f"INSERT INTO messages_with_menu (msg_id, user) VALUES ('{msg.message_id}', '{message.from_user.id}')")
    # await conn.commit()
    conn.close()


@dp.message(first_time.account)
async def first_time_account(message: Message, state: any):
    await state.update_data(account=message.text)
    data = await state.get_data()
    account = data['account']
    user = message.from_user.id
    club_id = message.text
    # if the message is not a number ask for the account again
    print(is_english_digits(account))
    if not is_english_digits(account) or not len(message.text) > 4:
        await message.answer("لطفا شناسه کاربری عددی خود را وارد کنید", parse_mode="MarkDown")
        return
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    # find the first unassigned wallet and assign it to the user
    wallet = ""
    try:
        async with conn.cursor() as cursor:
            await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to IS NULL LIMIT 1")
            wallet = await cursor.fetchone()
            wallet = wallet[0]
            await cursor.execute(f"UPDATE wallets SET assigned_to='{user}' WHERE address='{wallet}'")
        await conn.commit()
        # add the user to club_ids with the default club_id
        async with conn.cursor() as cursor:
            await cursor.execute(f"SELECT * FROM club_ids WHERE user='{user}' AND club_id='{message.text}'")
            club_id = await cursor.fetchone()
            if not club_id:
                await cursor.execute(f"INSERT INTO club_ids (club_id, user, is_default) VALUES ('{message.text}', '{user}', 1)")
                club_id = message.text
            else:
                club_id = club_id[1]
            # await cursor.execute(f"INSERT INTO club_ids (club_id, user, is_default) VALUES ('{club_id}', '{user}', 1)")
            await conn.commit()
            await cursor.execute(f"UPDATE wallets SET assigned_to='{user}' WHERE address='{wallet}'")
            await conn.commit()
            # await message.answer(f"لطفا مبلغ دلخواه خود را به این ولت واریز کنید , و سپس( درخواست بررسی شارژ ) را کلیک کنید\nارزهای قابل انتقال:\nUSDT TRC-20\nTRON\nحداقل مبلغ واریزی 20$ میباشد.\n-", parse_mode="MarkDown")

        await state.clear()
        # delete the menu
        photo = await generate_qr_code_from_google(wallet)
        print(photo)
        usdt_price = await get_usdt_price()
        with_price = f"قیمت هر تتر {usdt_price} تومان میباشد"
        msg = await message.answer_photo(photo, caption=f"این خرید مربوط به شارژ آیدی {club_id} می باشد\nکیف پول شما:\n`{wallet}`\nارز های قابل واریز به این کیف پول:\nUSDT (TRC-20)\nTron (TRX)\n❗️کیف پول مورد نظر تنها برای انجام یک تراکنش موفق هستش. لطفاً برای تراکنش بعدی، شارژ حساب را مجدداً باز کنید.\nفقط تراکنش های بالای 20  تتر و 200 ترون قابل شارژ و پیگیری خواهند بود و در غیر اینصورت قابل پیگیری نخواهد بود.\n\n{with_price}\nاین کیف پول تا ۵ ساعت آینده برای شما و تنها برای یک تراکنش معتبر است.\n-", parse_mode="MarkDown", reply_markup=laghv_barrasi_keyboard)

        # id
        # msg_id
        # user_id
        # wallet
        # valid
        # store the message id in wallet_message
        async with conn.cursor() as cursor:
            await cursor.execute(f"INSERT INTO wallet_message (msg_id, user_id, wallet, valid) VALUES ('{msg.message_id}', '{user}', '{wallet}', 1)")
        await conn.commit()

        # add incoming tx to db
        async with conn.cursor() as cursor:
            date = int(time.time())
            print("HI")
            await cursor.execute(f"INSERT INTO incoming_tx (date, user, dest_account, expired) VALUES ({date}, '{user}', '{club_id}', 0)")
        await conn.commit()
        await state.clear()
    except Exception as e:
        print(e)
        msg = await message.answer("در حال حاضر هیچ ولتی در دسترس نیست، لطفا کمی بعد مجدد تلاش کنید", parse_mode="MarkDown", keybaord=builder)
        await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=msg.message_id, reply_markup=builder)
        is_disabled, mode, start_message, admins = await get_settings()
        for admin in admins:
            try:
                await bot.send_message(admin, "توجه: هیچ ولتی برای اختصاص به کاربر جدید در دسترس نیست")
            except:
                pass

        await state.clear()


@dp.message(filters.Command(commands=["manual_transfer"]))
async def manual_transfer_handler(message: Message, command: filters.Command, state: any):
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        await message.answer("You are an admin", parse_mode="MarkDown")
        await message.answer("Enter the account you want to transfer to", parse_mode="MarkDown")
        await state.set_state(manual_transfer.account)


@dp.message(manual_transfer.account)
async def manual_transfer_account(message: Message, state: any):
    await state.update_data(account=message.text)

    await state.set_state(manual_transfer.amount)
    await message.answer("Enter the amount you want to transfer", parse_mode="MarkDown")


@dp.message(manual_transfer.amount)
async def manual_transfer_amount(message: Message, state: any):
    await state.update_data(amount=message.text)

    await state.set_state(manual_transfer.sure)
    await message.answer(f"Are you sure you want to transfer {message.text} to {message.text}?", parse_mode="MarkDown")


@dp.message(manual_transfer.sure)
async def manual_transfer_sure(message: Message, state: any):
    data = await state.get_data()
    account = data['account']
    amount = data['amount']
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    is_disabled, mode, start_message, admins = await get_settings()
    if message.from_user.id not in admins:
        await message.answer("You are not an admin", parse_mode="MarkDown")
        return
    else:
        if message.text.lower() == "yes":
            await message.answer("You are an admin", parse_mode="MarkDown")
            transfer(account, amount)
            await message.answer(f"{amount} transferred to {account}", parse_mode="MarkDown")
            await state.clear()
        else:
            await message.answer("Transfer not made", parse_mode="MarkDown")
            await state.clear()


@dp.callback_query(receive_payment.select_account)
async def receive_payment_select_account(query: types.CallbackQuery, state: any):
    if query.data == "cancel":
        await state.clear()
        await query.message.answer("عملیات لغو شد", parse_mode="MarkDown", reply_markup=builder)
        return

    message_id = query.message.message_id
    chat_id = query.message.chat.id
    await state.set_state(receive_payment.wallet)
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    cursor = await conn.cursor()
    user = query.from_user.id
    await cursor.execute(f"SELECT * FROM club_ids WHERE user='{user}'")
    user_accounts = await cursor.fetchall()
    user_accounts = [account[1] for account in user_accounts]
    conn.close()
    account_list = InlineKeyboardMarkup()
    if len(user_accounts) > 0:
        for account in user_accounts:
            account_list.row(InlineKeyboardButton(
                text=str(account), callback_data=str(account)))
        # add cancel
        account_list.row(InlineKeyboardButton(
            text="لغو", callback_data="cancel"))
    qm_message = await query.message.answer("لطفا شماره آیدی مورد نظر را وارد نمایید\n-", parse_mode="MarkDown", reply_markup=account_list.as_markup())
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    try:
        async with conn.cursor() as cursor:
            await cursor.execute(f"INSERT INTO messages_with_menu (msg_id, user) VALUES ('{qm_message.message_id}', '{user}')")
        await conn.commit()
    except:
        pass


@dp.callback_query(receive_payment.wallet)
async def receive_wallet_b(query: types.CallbackQuery, state: any):

    try:
        conn1 = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                       user=db_config['user'], password=db_config['password'],
                                       db=db_config['database'])

        async with conn1.cursor() as cursor:
            await cursor.execute(f"SELECT msg_id FROM messages_with_menu WHERE user='{user}'")
            qm_message = await cursor.fetchall()
            for msg in qm_message:
                await bot.delete_message(chat_id=query.message.chat.id, message_id=msg[0])
            await cursor.execute(f"DELETE FROM messages_with_menu WHERE user='{user}'")
        await conn1.commit()
        conn1.close()

    except:
        pass

    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    cursor = await conn.cursor()
    user = query.from_user.id
    if query.data == "cancel":
        await state.clear()
        await query.message.answer("عملیات لغو شد", parse_mode="MarkDown", reply_markup=builder)
        return
    # make the selected account default
    await cursor.execute(f"UPDATE club_ids SET is_default=1 WHERE club_id='{query.data}' AND user='{user}'")
    await conn.commit()
    await cursor.execute(f"UPDATE club_ids SET is_default=0 WHERE club_id!='{query.data}' AND user='{user}'")
    await conn.commit()
    print("hi")
    await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to='{user}'")
    wallet = await cursor.fetchone()
    # create incoming_tx
    date2 = int(time.time())
    # insert date, user, dest_account and expired(0) into incoming_tx
    conn.close()
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    async with conn.cursor() as cursor:
        await cursor.execute(f"INSERT INTO incoming_tx (date, user, dest_account, expired) VALUES ({date2}, '{user}', '{query.data}', 0)")
    await conn.commit()
    print(wallet)
    # print(qm_message)
    if wallet:
        print("ok")
        # await query.message.answer(f"لطفا مبلغ دلخواه خود را به این ولت واریز کنید , و سپس( درخواست بررسی شارژ ) را کلیک کنید\nارزهای قابل انتقال:\nUSDT TRC-20\nTRON\nحداقل مبلغ واریزی 20$ میباشد.\n-", parse_mode="MarkDown")
        # delete the menu
        photo = await generate_qr_code_from_google(wallet[0])
        print(photo)
        usdt_price = await get_usdt_price()
        with_price = f"قیمت هر تتر {usdt_price} تومان میباشد"

        msg = await query.message.answer_photo(photo, caption=f"کیف پول شمااین خرید مربوط به شارژ آیدی {query.data} می باشد\n:\n`{wallet[0]}`\nارز های قابل واریز به این کیف پول:\nUSDT (TRC-20)\nTron (TRX)\n❗️کیف پول مورد نظر تنها برای انجام یک تراکنش موفق هستش. لطفاً برای تراکنش بعدی، شارژ حساب را مجدداً باز کنید.\nفقط تراکنش های بالای 20  تتر و 200 ترون قابل شارژ و پیگیری خواهند بود و در غیر اینصورت قابل پیگیری نخواهد بود.\n\n{with_price}\nاین  کیف پول تا ۵ ساعت و فقط برای یک واریزی معتبر می باشد.\n-", parse_mode="MarkDown", reply_markup=laghv_barrasi_keyboard)
        try:
            await bot.edit_message_reply_markup(query.message.chat.id, query.message.message_id, reply_markup=None)
        except:
            pass

        async with conn.cursor() as cursor:
            await cursor.execute(f"INSERT INTO wallet_message (msg_id, user_id, wallet, valid) VALUES ('{msg.message_id}', '{user}', '{wallet[0]}', 1)")
        await conn.commit()

    else:
        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                      user=db_config['user'], password=db_config['password'],
                                      db=db_config['database'])
        cursor = await conn.cursor()
        await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to IS NULL")
        results = await cursor.fetchall()
        if results:
            random_address = random.choice(results)[0]
            print(random_address)
        wallet = random_address
        if wallet:
            await cursor.execute(f"UPDATE wallets SET assigned_to='{user}' WHERE address='{wallet}'")
            await conn.commit()
            # await query.message.answer(f"لطفا مبلغ دلخواه خود را به این ولت واریز کنید , و سپس( درخواست بررسی شارژ ) را کلیک کنید\nارزهای قابل انتقال:\nUSDT TRC-20\nTRON\nحداقل مبلغ واریزی 20$ میباشد.\n-", parse_mode="MarkDown")
            # delete the menu
            photo = await generate_qr_code_from_google(wallet)
            print(photo)
            usdt_price = await get_usdt_price()
            with_price = f"قیمت هر تتر {usdt_price} تومان میباشد"

            msg = await query.message.answer_photo(photo, caption=f"این خرید مربوط به شارژ آیدی {query.data} می باشد\nکیف پول شما:\n`{wallet}`\nارز های قابل واریز به این کیف پول:\nUSDT (TRC-20)\nTron (TRX)\n❗️کیف پول مورد نظر تنها برای انجام یک تراکنش موفق هستش. لطفاً برای تراکنش بعدی، شارژ حساب را مجدداً باز کنید.\nفقط تراکنش های بالای 20  تتر و 200 ترون قابل شارژ و پیگیری خواهند بود و در غیر اینصورت قابل پیگیری نخواهد بود.\n\n{with_price}\nاین کیف پول به مدت ۵ ساعت و تنها برای یک واریزی معتبر می باشد\n-", parse_mode="MarkDown", reply_markup=laghv_barrasi_keyboard)
            try:
                await bot.edit_message_reply_markup(query.message.chat.id, query.message.message_id, reply_markup=None)
            except:
                pass
            async with conn.cursor() as cursor:
                await cursor.execute(f"INSERT INTO wallet_message (msg_id, user_id, wallet, valid) VALUES ('{msg.message_id}', '{user}', '{wallet}', 1)")
            await conn.commit()

        else:
            await query.message.answer("هیچ کیف پولی برای شما وجود ندارد", parse_mode="MarkDown", keybaord=builder)

    conn.close()
    await state.clear()


@dp.message(receive_payment.wallet)
async def receive_payment_wallet(message: Message, state: any):
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    cursor = await conn.cursor()
    user = message.from_user.id
    try:
        conn1 = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                       user=db_config['user'], password=db_config['password'],
                                       db=db_config['database'])

        async with conn1.cursor() as cursor:
            await cursor.execute(f"SELECT msg_id FROM messages_with_menu WHERE user='{user}'")
            qm_message = await cursor.fetchall()
            for msg in qm_message:
                await bot.delete_message(chat_id=message.chat.id, message_id=msg[0])
            await cursor.execute(f"DELETE FROM messages_with_menu WHERE user='{user}'")
        await conn1.commit()
        conn1.close()

    except:
        pass
    conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                  user=db_config['user'], password=db_config['password'],
                                  db=db_config['database'])
    cursor = await conn.cursor()
    # if the message is not a number ask for the account again
    print(is_english_digits(message.text))
    if not is_english_digits(message.text) or not len(message.text) > 4:
        await message.answer("لطفا شناسه کاربری عددی خود را وارد کنید", parse_mode="MarkDown")
        return

    # add the account to the club_ids if the same user doesn't have the same account
    await cursor.execute(f"SELECT * FROM club_ids WHERE user='{user}' AND club_id='{message.text}'")
    club_id = await cursor.fetchone()
    if not club_id:
        await cursor.execute(f"INSERT INTO club_ids (club_id, user, is_default) VALUES ('{message.text}', '{user}', 1)")
        club_id = message.text
    await conn.commit()
    await cursor.execute(f"UPDATE club_ids SET is_default=0 WHERE club_id!='{message.text}' AND user='{user}'")
    await conn.commit()
    await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to='{user}'")
    wallet = await cursor.fetchone()
    await state.clear()
    print(wallet)
    if wallet:

        # await message.answer(f"لطفا مبلغ دلخواه خود را به این ولت واریز کنید , و سپس( درخواست بررسی شارژ ) را کلیک کنید\nارزهای قابل انتقال:\nUSDT TRC-20\nTRON\nحداقل مبلغ واریزی 20$ میباشد.\n-", parse_mode="MarkDown")
        photo = await generate_qr_code_from_google(wallet[0])
        print(photo)

        usdt_price = await get_usdt_price()
        with_price = f"قیمت هر تتر {usdt_price} تومان میباشد"

        msg = await message.answer_photo(photo, caption=f"این خرید مربوط به شارژ آیدی {club_id} می باشد\nکیف پول شما:\n`{wallet[0]}`\nارز های قابل واریز به این کیف پول:\nUSDT (TRC-20)\nTron (TRX)\n❗️کیف پول مورد نظر تنها برای انجام یک تراکنش موفق هستش. لطفاً برای تراکنش بعدی، شارژ حساب را مجدداً باز کنید.\nفقط تراکنش های بالای 20  تتر و 200 ترون قابل شارژ و پیگیری خواهند بود و در غیر اینصورت قابل پیگیری نخواهد بود.\n\n{with_price}\nاین کیف پول تا ۵ ساعت و تنها برای یک واریزی معتبر میباشد.-", parse_mode="MarkDown", reply_markup=laghv_barrasi_keyboard)
        try:
            await bot.edit_message_reply_markup(message.chat.id, message.message_id, reply_markup=None)
        except:
            pass

        async with conn.cursor() as cursor:
            await cursor.execute(f"INSERT INTO wallet_message (msg_id, user_id, wallet, valid) VALUES ('{msg.message_id}', '{user}', '{wallet[0]}', 1)")
        await conn.commit()

    else:
        await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to IS NULL")
        results = await cursor.fetchall()
        if results:
            random_address = random.choice(results)[0]
            print(random_address)
        wallet = random_address
        # fetch random wallet

        # wallet = await cursor.fetchone()
        if wallet:
            await cursor.execute(f"UPDATE wallets SET assigned_to='{user}' WHERE address='{wallet}'")
            await conn.commit()
            # await message.answer(f"لطفا مبلغ دلخواه خود را به این ولت واریز کنید , و سپس( درخواست بررسی شارژ ) را کلیک کنید\nارزهای قابل انتقال:\nUSDT TRC-20\nTRON\nحداقل مبلغ واریزی 20$ میباشد.\n-", parse_mode="MarkDown")
            photo = await generate_qr_code_from_google(wallet)
            print(photo)

            usdt_price = await get_usdt_price()
            with_price = f"قیمت هر تتر {usdt_price} تومان میباشد"

            msg = await message.answer_photo(photo, caption=f"این خرید مربوط به شارژ آیدی {club_id} می باشد\n\nکیف پول شما:\n`{wallet}`\nارز های قابل واریز به این کیف پول:\nUSDT (TRC-20)\nTron (TRX)\n❗️کیف پول مورد نظر تنها برای انجام یک تراکنش موفق هستش. لطفاً برای تراکنش بعدی، شارژ حساب را مجدداً باز کنید.\nفقط تراکنش های بالای 20  تتر و 200 ترون قابل شارژ و پیگیری خواهند بود و در غیر اینصورت قابل پیگیری نخواهد بود.\n\n{with_price}\nاین کیف پول به مدت ۵ ساعت و تنها برای یک واریزی معتبر میباشد.-", parse_mode="MarkDown", reply_markup=laghv_barrasi_keyboard)
            try:
                await bot.edit_message_reply_markup(message.chat.id, message.message_id, reply_markup=None)
            except:
                pass

            async with conn.cursor() as cursor:
                await cursor.execute(f"INSERT INTO wallet_message (msg_id, user_id, wallet, valid) VALUES ('{msg.message_id}', '{user}', '{wallet}', 1)")
            await conn.commit()

        else:
            await message.answer("هیچ کیف پولی برای شما وجود ندارد", parse_mode="MarkDown", keybaord=builder)

    conn.close()
    await state.clear()


@dp.callback_query()
async def callback_handler(query: types.CallbackQuery, state: any):
    message_id = query.message.message_id
    chat_id = query.message.chat.id
    logging.info(f"CallbackQuery: {query.data}")
    print(query.data)
    try:
        await bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
    except:
        pass

    if query.data == "cancel":
        await state.clear()
        await query.message.answer("عملیات لغو شد", parse_mode="MarkDown", reply_markup=builder)

    elif query.data == "receive_wallet_b":
        await state.clear()
        await state.set_state(first_time.account)
        await query.message.answer("لطفا شناسه کاربری عددی خود در JackpotClub را وارد کنید", parse_mode="MarkDown")

    elif query.data == "شارژ حساب":
        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                      user=db_config['user'], password=db_config['password'],
                                      db=db_config['database'])
        cursor = await conn.cursor()
        user = query.from_user.id
        await cursor.execute(f"SELECT * FROM incoming_tx WHERE user='{user}' AND expired=0")
        incoming_tx = await cursor.fetchone()
        if incoming_tx and incoming_tx[1] + 18000 > int(time.time()):
            expired_date = incoming_tx[1] + 18000
            # convert to human readable date in tehran timezone
            import datetime
            expired_date = datetime.datetime.fromtimestamp(
                expired_date, pytz.timezone('Asia/Tehran')).strftime('%Y-%m-%d %H:%M:%S')

            cancel_tx_keyboard = InlineKeyboardMarkup()
            cancel_tx_keyboard.row(InlineKeyboardButton(
                text="لغو تراکنش", callback_data="cancel_tx"))
            cancel_tx_keyboard.row(InlineKeyboardButton(
                text="بررسی واریزی", callback_data="check_deposit"))
            tx_keyboard = cancel_tx_keyboard.as_markup()
            await query.message.answer(f"شما یک درخواست شارژ فعال دارید، اگر میخواهید درخواست جدیدی ارسال کنید، لطفا درخواست فعلی خود را لغو کنید\nاین تراکنش به صورت خودکار در تاریخ {expired_date} منقضی خواهد شد.\n-", parse_mode="MarkDown", reply_markup=tx_keyboard)
        else:
            await state.set_state(receive_payment.select_account)
            # دریافت کیف پول Button
            # Cancel
            keyboard = InlineKeyboardMarkup().row(InlineKeyboardButton(text="دریافت کیف پول", callback_data="receive_wallet_b")
                                                  ).row(InlineKeyboardButton(text="لغو", callback_data="cancel")).as_markup()
            await query.message.answer("جهت دریافت کیف پول روی دکمه زیر کلیک کنید", parse_mode="MarkDown", reply_markup=builder)
            # find if user has any wallet address assigned, if not, choose one and assign it and send it

    elif query.data == "cancel_tx":
        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                      user=db_config['user'], password=db_config['password'],
                                      db=db_config['database'])
        cursor = await conn.cursor()
        user = query.from_user.id
        await cursor.execute(f"UPDATE incoming_tx SET expired=1 WHERE user='{user}' AND expired=0")
        await conn.commit()
        conn.close()

        await query.message.answer("درخواست شارژ فعال لغو شد", parse_mode="MarkDown", reply_markup=builder)
        await state.clear()

        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                      user=db_config['user'], password=db_config['password'],
                                      db=db_config['database'])
        cursor = await conn.cursor()
        # find the assigned wallet to the user and make the assigned_to NULL
        await cursor.execute(f"SELECT address FROM wallets WHERE assigned_to='{user}'")
        wallet = await cursor.fetchone()
        if wallet:
            await cursor.execute(f"UPDATE wallets SET assigned_to=NULL WHERE address='{wallet[0]}'")
            await conn.commit()

        # id
        # msg_id
        # user_id
        # wallet
        # valid

        # find the relevant message in wallet_message and delete it and set valid to 0

        await cursor.execute(f"SELECT msg_id FROM wallet_message WHERE user_id='{user}' AND valid=1")
        msg_id = await cursor.fetchone()
        if msg_id:
            await cursor.execute(f"UPDATE wallet_message SET valid=0 WHERE user_id='{user}'")
            await conn.commit()
            try:
                await bot.delete_message(chat_id=query.message.chat.id, message_id=msg_id[0])
            except:
                pass

        conn.close()

    elif query.data == "بررسی واریزی جدید به کیف پول TRX/USDT":
        response = await check_deposit(query.from_user.id)
        if not response:
            await query.answer("در حال حاضر واریزی جدیدی به ولت مورد نظر شما انجام نشده است.", parse_mode="MarkDown", reply_markup=builder)

    elif query.data == "check_deposit":
        conn = await aiomysql.connect(host=db_config['host'], port=db_config['port'],
                                      user=db_config['user'], password=db_config['password'],
                                      db=db_config['database'])
        cursor = await conn.cursor()
        user = query.from_user.id
        await cursor.execute(f"SELECT * FROM incoming_tx WHERE user='{user}' AND expired=0")
        incoming_tx = await cursor.fetchone()
        cancel_tx_keyboard = InlineKeyboardMarkup()
        cancel_tx_keyboard.row(InlineKeyboardButton(text="لغو تراکنش", callback_data="cancel_tx"),
                               InlineKeyboardButton(text="بررسی واریزی", callback_data="check_deposit"))
        cancel_tx_keyboard = cancel_tx_keyboard.as_markup()
        if incoming_tx and incoming_tx[1] + 18000 > int(time.time()):
            cancel_tx_keyboard = InlineKeyboardMarkup()
            cancel_tx_keyboard.row(InlineKeyboardButton(text="لغو تراکنش", callback_data="cancel_tx"), InlineKeyboardButton(
                text="بررسی واریزی", callback_data="check_deposit"))
            cancel_tx_keyboard = cancel_tx_keyboard.as_markup()

            # await query.answer("در حال بررسی واریز های جدید به کیف پول\nدر صورت وجود واریزی جدید پیام جدید به شما خواهد ارسال شد\n-", parse_mode="MarkDown", reply_markup=cancel_tx_keyboard)
            try:
                await bot.edit_message_reply_markup(chat_id, message_id, reply_markup=cancel_tx_keyboard)
            except:
                pass
            # await check_deposit(query.from_user.id)
            response = await check_deposit(query.from_user.id)
            if not response:
                await query.answer("در حال حاضر واریزی جدیدی به ولت مورد نظر شما انجام نشده است.", parse_mode="MarkDown", reply_markup=builder)

        else:
            keyboard = InlineKeyboardMarkup().row(InlineKeyboardButton(
                text="شارژ حساب", callback_data="شارژ حساب")).as_markup()
            # await query.answer("در حال بررسی واریز های جدید به کیف پول\nدر صورت وجود واریزی جدید پیام جدید به شما خواهد ارسال شد\n-", parse_mode="MarkDown", reply_markup=builder)
            try:
                await bot.edit_message_reply_markup(chat_id, message_id, reply_markup=cancel_tx_keyboard)
            except:
                pass
            response = await check_deposit(query.from_user.id)
            if not response:
                await query.answer("در حال حاضر واریزی جدیدی به ولت مورد نظر شما انجام نشده است.", parse_mode="MarkDown", reply_markup=builder)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

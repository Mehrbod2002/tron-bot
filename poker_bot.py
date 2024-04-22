import requests
import pymysql
from config import *
from aiogram import Bot
import time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
bot = Bot(token=token)


url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush?deviceId=09c3b664033d47428133a9cd99f09895&apikey=1abba6b5d1f4436f963b1599eb9317f2"
buttons = ["شارژ حساب"]
keyboard_markup = InlineKeyboardMarkup()

for button_text in buttons:
    keyboard_markup.add(InlineKeyboardButton(
        text=button_text, callback_data=button_text))


async def async_transfer(account, amount):
    additional_1 = f"title={account}"
    additional_2 = f"text={amount}"
    additional_2 = additional_2.split(
        ".")[0] + "." + additional_2.split(".")[1][:2]
    requests.get(url + "&" + additional_1 + "&" + additional_2)
    return "Transfer successful"


async def go():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * from transactions where processed = 0")
    transactions = cursor.fetchone()
    conn.close()
    print(transactions)
    user_tg = transactions[5]
    print(user_tg)
    in_tomans = transactions[7]
    chips = in_tomans / 100000
    max_two_digits = str(chips).split(".")[1][:2]
    chips = str(chips).split(".")[0] + "." + max_two_digits
    print(user_tg, chips, in_tomans)

    # change the processed to 1
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE transactions SET processed = 1 where id = {transactions[0]}")
    conn.commit()
    user_id = cursor.execute(
        f"SELECT * from incoming_tx where user = {user_tg} and expired = 0")
    user_id = cursor.fetchall()
    wallet = transactions[2]
    dest_account = ""
    in_usd = transactions[6]
    nerkh_usd = transactions[8]
    coin = transactions[3]
    amount = transactions[11]
    print(user_id)
    # find the last one that its date[1] is less than 5 hours ago and take its dest_account and set other ones as expired
    for i in user_id:
        if i[1] < transactions[1] - 5*60*60:
            cursor.execute(
                f"UPDATE incoming_tx SET expired = 1 where id = {i[0]}")
            conn.commit()
        else:
            dest_account = i[3]
            break
    if dest_account == "":
        # find admins
        cursor.execute("SELECT * from admins")
        admins = cursor.fetchall()
        for admin in admins:
            await bot.send_message(admin[1], f"یک واریزی به ولت `{transactions[2]}` به مبلغ {in_tomans} تومان برای کاربر {user_tg} انجام شده است اما هیچ حسابی برای انتقال چیپ به این کاربر وجود ندارد\nمبلغ به دلار: {transactions[6]}\nلینک تراکنش:\nhttps://tronscan.org/#/transaction/{transactions[9]}", parse_mode='MarkDown')
    else:
        cursor.execute("SELECT * from admins")
        admins = cursor.fetchall()
        await async_transfer(dest_account, chips)
        await bot.send_message(user_tg, f"حساب شماره {dest_account} در حال شارژ شدن به مقدار {chips} چیپ میباشد\nاین فرآیند ممکن است بین 1 تا 5 دقیقه زمان ببرد.\nبا آرزوی برد برای شما!\n\n-", reply_markup=keyboard_markup)
        for admin in admins:
            try:
                text = f"مبلغ {amount} {coin} معادل {in_usd} دلار به کیف پول `{wallet}` انتقال یافت\nنرخ دلار: {nerkh_usd}\nمعادل چیپ واریزی: {chips}\nحساب مقصد: {dest_account}\nلینک تراکنش:\nhttps://tronscan.org/#/transaction/{transactions[9]}"
                await bot.send_message(admin[1], text, parse_mode='MarkDown')
            except Exception as e:
                with open("error.txt", "a") as f:
                    f.write(str(e) + "\n")

        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE incoming_tx SET expired = 1 where user = {user_tg}")
        conn.commit()
        conn.close()

        # now we need to NULL the assigned_to in the wallet table to make it available
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE wallets SET assigned_to = NULL where address = '{wallet}'")
        conn.commit()
        # send a message to the user that their wallet is expired
        # try:
        #     await bot.send_message(user_tg, f"لطفا توجه فرمایید که کیف پول به آدرس `{wallet}` یکبار مصرف می باشد. جهت واریز های بعدی لطفا کیف پول جدید دریافت فرمایید.\n-", reply_markup=keybaord)
        # except:
        #     pass
        admins = cursor.execute("SELECT * from admins")
        admins = cursor.fetchall()
        for admin in admins:
            try:
                await bot.send_message(admin[1], f"کیف پول {wallet} پس از انجام تراکنش منقضی شد و قابل استفاده مجدد می باشد ")
            except:
                pass

        # id
        # msg_id
        # user_id
        # wallet
        # valid

        # find the relevant message in wallet_message and delete it and set valid to 0
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT msg_id FROM wallet_message WHERE user_id='{user_tg}' AND valid=1")
        msg_id = cursor.fetchone()
        print(msg_id)
        if msg_id:
            cursor.execute(
                f"UPDATE wallet_message SET valid=0 WHERE user_id='{user_tg}'")
            conn.commit()

            try:
                await bot.delete_message(chat_id=user_tg, message_id=msg_id[0])
            except Exception as e:
                with open("error.txt", "a") as f:
                    f.write(str(e) + "\n")
                pass

        conn.close()

        return "done"


async def check_wallets():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * from wallets where assigned_to != '' and is_locked = 0")
    wallets = cursor.fetchall()
    # now we need to find the wallets that have expired but the expired value is not set to 1 and set them to 1 and send a message to the user that the wallet has expired and inform the admins about it
    for wallet in wallets:
        cursor.execute(
            f"SELECT * from incoming_tx where user = {wallet[4]} and expired = 0")
        incoming_tx = cursor.fetchall()
        for tx in incoming_tx:
            if tx[1] < time.time() - 5*60*60:
                cursor.execute(
                    f"UPDATE incoming_tx SET expired = 1 where user = {tx[2]}")
                conn.commit()
                try:
                    await bot.send_message(wallet[4], f"کیف پول `{wallet[1]}` که پیشتر به شما اختصاص داده شده بود منقضی شد.\nلطفا در صورت نیاز به شارژ حساب کلاب خود از بات کیف پول جدید دریافت کنید\n", reply_markup=keyboard_markup, parse_mode='MarkDown')
                except:
                    pass
                cursor.execute("SELECT * from admins")
                admins = cursor.fetchall()
                cursor.execute(
                    f"UPDATE wallets SET assigned_to = NULL where id = {wallet[0]}")
                conn.commit()
                for admin in admins:
                    try:
                        await bot.send_message(admin[1], f"کیف پول {wallet[1]} منقضی شد ")
                    except:
                        pass

    conn.close()


async def main():
    try:
        await go()
    except Exception as e:
        with open("error.txt", "a") as f:
            f.write(str(e) + "\n")
    try:
        await check_wallets()
    except Exception as e:
        with open("error.txt", "a") as f:
            f.write(str(e) + "\n")

    with open("lock.txt", "w") as f:
        f.write("0")

if __name__ == "__main__":
    import asyncio
    if open("lock.txt", "r").read() == "1":
        print("Already running")
        exit()
    else:
        try:
            with open("lock.txt", "w") as f:
                f.write("1")
            asyncio.run(main())
        except Exception as e:
            with open("lock.txt", "w") as f:
                f.write("0")
            print(e)

import os
import logging
import sqlite3
import pandas as pd
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# SCHIMBĂ AICI CU ID-UL TĂU (vezi pasul 6 cum îl afli)
DISPECER_ID = 123456789  # <--- înlocuiește cu ID-ul tău real

DIRECTION, DATE, CITIES, SEATS, PHONE = range(5)
logging.basicConfig(level=logging.INFO)

def init_db():
    conn = sqlite3.connect('anchete.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS anchete
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
                  direction TEXT, data TEXT, ruta TEXT, locuri INTEGER, telefon TEXT,
                  creat_la TEXT, status TEXT)''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TRIMITE ȘI ID-UL TĂU LA PRIMUL MESAJ (ca să-l afli ușor)
    if update.message.from_user.id not in [123456789, DISPECER_ID]:  # doar prima oară
        await update.message.reply_text(f"ID-ul tău este: {update.effective_user.id}\nTrimite-l adminului să-l pună în cod.")
    
    keyboard = [[InlineKeyboardButton("Moldova → Germania", callback_data="md_de")],
                [InlineKeyboardButton("Germania → Moldova", callback_data="de_md")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Bună! Completează cererea de transport:\nAlege direcția:", reply_markup=reply_markup)
    return DIRECTION

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['dir'] = "Moldova → Germania" if query.data == "md_de" else "Germania → Moldova"
    await query.edit_message_text(f"Direcție: {context.user_data['dir']}\n\nData aproximativă (ex: 25-30 decembrie):")
    return DATE

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['data'] = update.message.text
    await update.message.reply_text("Ruta exactă (ex: Chișinău → München):")
    return CITIES

async def cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ruta'] = update.message.text.strip()
    await update.message.reply_text("Câte locuri cauți/oferi?")
    return SEATS

async def seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['locuri'] = int(update.message.text)
        await update.message.reply_text("Număr de telefon (obligatoriu):")
        return PHONE
    except:
        await update.message.reply_text("Te rog scrie doar un număr (ex: 2)")
        return SEATS

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['telefon'] = update.message.text.strip()
    user = update.effective_user

    # Salvează în baza de date
    conn = sqlite3.connect('anchete.db')
    c = conn.cursor()
    c.execute("INSERT INTO anchete VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
        user.id, user.username or user.first_name,
        context.user_data['dir'], context.user_data['data'],
        context.user_data['ruta'], context.user_data['locuri'],
        context.user_data['telefon'], datetime.now().strftime("%d.%m.%Y %H:%M"), "nou"
    ))
    ancheta_id = c.lastrowid
    conn.commit()
    conn.close()

    # Mesaj pentru client
    await update.message.reply_text("Mulțumesc! Cererea ta a fost trimisă dispecerului.\nTe vom contacta în curând! ✅")

    # Mesaj pentru dispecer
    text_disp = (f"NOUĂ CERERE #{ancheta_id}\n\n"
                 f"Client: @{user.username or '-'} ({user.first_name})\n"
                 f"Direcție: {context.user_data['dir']}\n"
                 f"Data: {context.user_data['data']}\n"
                 f"Rută: {context.user_data['ruta']}\n"
                 f"Locuri: {context.user_data['locuri']}\n"
                 f"Telefon: {context.user_data['telefon']}\n"
                 f"Data: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    keyboard = [[InlineKeyboardButton("Apelat", callback_data=f"ok_{ancheta_id}")]]
    await context.bot.send_message(DISPECER_ID, text_disp, reply_markup=InlineKeyboardMarkup(keyboard))

    return ConversationHandler.END

# Buton "Apelat"
async def apelat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(query.message.text + "\n\n✅ APELAT ȘI REZOLVAT")

# Comandă /excel - doar pentru tine (dispecerul)
async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != DISPECER_ID:
        return
    conn = sqlite3.connect('anchete.db')
    df = pd.read_sql_query("SELECT * FROM anchete", conn)
    conn.close()
    df.to_excel('anchete.xlsx', index=False)
    await update.message.reply_document(open('anchete.xlsx', 'rb'), caption="Toate anchetele până acum")

def main():
    init_db()
    app = Application.builder().token(os.getenv("TOKEN")).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            DIRECTION: [CallbackQueryHandler(button)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date)],
            CITIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cities)],
            SEATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, seats)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(apelat, pattern="^ok_"))
    app.add_handler(CommandHandler("excel", export_excel))

    print("Botul dispecer rulează...")
    app.run_polling()

if __name__ == "__main__":
    main()
